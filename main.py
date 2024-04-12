import csv
import os
import requests
import logging
import argparse
import time
import math

# Set constants
GITHUB_API_URL = 'https://api.github.com'
GENERIC_SLEEP_TIME_SECONDS = 1

def is_secret_scanning_enabled(base_url, pat, org, repo):
    # Make a request to the GitHub API to check if GHAS is enabled
    headers = {'Authorization': f'Bearer {pat}', 'Accept': 'application/vnd.github.v3+json', 'Content-Type': 'application/json'}
    response = requests.get(f'{base_url}/repos/{org}/{repo}', headers=headers)

    # Ensure the request was successful
    if response.status_code != 200:
        logging.error(f"Failed to fetch repository data: {response.status_code}, {response.text}")
        return False

    # Check the 'secret_scanning' status field in the response
    repo_info = response.json()
    ss_enabled = 'enabled' in repo_info['security_and_analysis']['secret_scanning']['status']
    return ss_enabled

def get_secret_scanning_alerts_from_repo(url, pat, page, alerts):
    while url:
        logging.debug(f"Fetching secret scanning alerts (page {page} from {url})")
        headers = {'Authorization': f'Bearer {pat}', 'Accept': 'application/vnd.github.v3+json', 'Content-Type': 'application/json'}
        params = {'per_page': 100}
        response = requests.get(url, headers=headers, params=params)

        # Handle rate limits
        if response.status_code == 403 or response.status_code == 429:
            logging.warning(f"Rate limit encountered: {response.status_code}, {response.text}")
            handle_rate_limits(response)

        # Ensure the request was successful
        elif response.status_code != 200:
            logging.error(f"Failed to fetch secret scanning alerts: {response.status_code}, {response.text}")
            return alerts

        # Paginate through the results
        else:
            # Add the alerts to the list
            alerts.extend(response.json())

            # Check if there is a next page
            link_header = response.headers.get('Link')
            if link_header:
                links = link_header.split(', ')
                url = None
                for link in links:
                    if 'rel="next"' in link:
                        url = link[link.index('<')+1:link.index('>')]
                        page += 1
            else:
                url = None

    return alerts

def handle_rate_limits(response):
    # Log x-ratelimit-remaining and sleep if it's low
    rate_limit_remaining = response.headers.get('X-RateLimit-Remaining')
    rate_limit_reset = response.headers.get('X-RateLimit-Reset')
    logging.debug(f"Rate limit remaining: {rate_limit_remaining}")
    
    # Check for primary rate limit
    if int(rate_limit_remaining) == 0:
        current_time = math.floor(time.time())
        reset_time = int(rate_limit_reset) - int(current_time) + 5
        if reset_time > 0:
            logging.warning(f"Primary rate limit reached ({rate_limit_remaining} requests remaining). Sleeping for {reset_time} second(s) until rate limit is reset...")
            time.sleep(reset_time)
    
    # Check secondary rate limit
    elif response.headers.get('retry-after'):
        retry_after = int(response.headers.get('retry-after')) + 5
        logging.warning(f"Secondary rate limit reached. Sleeping for {retry_after} second(s) until rate limit is reset...")
        time.sleep(int(retry_after))
    
    # Sleep for generic time
    else:
        logging.warning(f"Unknown rate limit reached. Sleeping for {GENERIC_SLEEP_TIME_SECONDS} second(s)...")
        time.sleep(GENERIC_SLEEP_TIME_SECONDS)

def update_secret_scanning_alert(url, pat, state, resolution, resolution_comment):
    # Update the secret scanning alert with the given state and resolution
    headers = {'Authorization': f'Bearer {pat}', 'Accept': 'application/vnd.github.v3+json', 'Content-Type': 'application/json'}
    data = {'state': state, 'resolution': resolution, 'resolution_comment': resolution_comment}
    response = requests.patch(url, headers=headers, json=data)
    while True:
        # Handle rate limits
        if response.status_code == 403 or response.status_code == 429:
            logging.warning(f"Rate limit encountered: {response.status_code}, {response.text}")
            handle_rate_limits(response)

        # Ensure the request was successful
        elif response.status_code != 200:
            logging.error(f"Failed to update secret scanning alert: {response.status_code}, {response.text}")
            return False
        
        # Return success
        else:
            logging.debug(f"Successfully updated secret scanning alert: {url}")
            return True

def main():
    # Set up logging
    logging.basicConfig(level=logging.DEBUG)

    # Fetch environment variables
    source_api_url = os.getenv('SOURCE_API_URL')
    source_pat = os.getenv('SOURCE_PAT')
    destination_pat = os.getenv('DESTINATION_PAT')

    # Set up command line argument parsing
    parser = argparse.ArgumentParser(description='Migrate secret scanning alert state between repositories')
    parser.add_argument('--csv', type=str, help='Path to the CSV file')
    parser.add_argument('--dry-run', type=str, default='true', help='Dry run mode')
    args = parser.parse_args()
    args.dry_run = False if args.dry_run.lower() == 'false' else True

    # Check if environment variables are set
    if not all([source_api_url, source_pat, destination_pat]):
        logging.error("Please set all required environment variables: SOURCE_API_URL, SOURCE_PAT, DESTINATION_PAT")
        exit(1)

    # Set counters for summary and dry run mode
    matched_alert_count = 0 # count of alerts that were matched between the source and destination repos
    matched_closed_alert_count = 0 # count of alerts that were closed in the source repo and open in the target repo

    # Open the CSV file
    with open(args.csv, 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            try:
                # Extract data from each row
                source_org = row['Source Org']
                source_repo = row['Source Repo']
                destination_org = row['Destination Org']
                destination_repo = row['Destination Repo']
            except KeyError as e:
                print(f"Error: CSV file does not have a column named '{e.args[0]}'. Please check the CSV file.")
                break

            # Check is secret scanning is enabled in the source repo
            logging.debug(f"Checking if secret scanning is enabled for {source_org}/{source_repo}")
            source_repo_ghas_status = is_secret_scanning_enabled(source_api_url, source_pat, source_org, source_repo)

            if not source_repo_ghas_status:
                logging.warning(f"Secret scanning is not enabled for {source_org}/{source_repo}. Skipping this repository...")
                continue

            # Check is secret scanning is enabled in the destination repo
            logging.debug(f"Checking if secret scanning is enabled for {destination_org}/{destination_repo}")
            destination_repo_ghas_status = is_secret_scanning_enabled(GITHUB_API_URL, destination_pat, destination_org, destination_repo)

            if not destination_repo_ghas_status:
                logging.warning(f"Secret scanning is not enabled for {destination_org}/{destination_repo}. Skipping this repository...")
                continue

            # Get all secret scanning alerts for the source & destination repos
            logging.debug(f"Fetching secret scanning alerts for {source_org}/{source_repo}")
            source_secrets_url = f'{source_api_url}/repos/{source_org}/{source_repo}/secret-scanning/alerts'
            source_alerts = get_secret_scanning_alerts_from_repo(source_secrets_url, source_pat, 1, [])
            if not source_alerts:
                logging.warning(f"No secret scanning alerts found for {source_org}/{source_repo}. Skipping this repository...")
                continue

            logging.debug(f"Fetching secret scanning alerts for {destination_org}/{destination_repo}")
            destination_secrets_url = f'{GITHUB_API_URL}/repos/{destination_org}/{destination_repo}/secret-scanning/alerts'
            destination_alerts = get_secret_scanning_alerts_from_repo(destination_secrets_url, destination_pat, 1, [])
            if not destination_alerts:
                logging.warning(f"No secret scanning alerts found for {destination_org}/{destination_repo}. Skipping this repository...")
                continue

            # Match alert IDs between source and destination repos based on pattern name and value
            source_alerts_dict = {}
            destination_alerts_dict = {}

            # Populate the source_alerts_dict
            for source_alert in source_alerts:
                key = (source_alert['secret_type'], source_alert['secret'])  # Create a tuple to use as the key
                source_alerts_dict[key] = {
                    'number': source_alert['number'],
                    'state': source_alert.get('state'),
                    'resolution': source_alert.get('resolution'),
                    'resolution_comment': source_alert.get('resolution_comment'),
                    'resolved_by': source_alert.get('resolved_by'),
                    'resolved_at': source_alert.get('resolved_at'),
                }

            # Populate the target_alerts_dict and find matches
            for destination_alert in destination_alerts:
                key = (destination_alert['secret_type'], destination_alert['secret'])  # Create a tuple to use as the key
                destination_alerts_dict[key] = destination_alert['number']
                if key in source_alerts_dict:
                    logging.debug(f"Match found: source {source_org}/{source_repo} alert ID {source_alerts_dict[key]['number']} -> destination {destination_org}/{destination_repo} alert ID {destination_alerts_dict[key]}")
                    matched_alert_count += 1

                    # Check if alert is closed in the source repo and open in destination repo
                    if source_alerts_dict[key]['state'] == 'resolved' and destination_alert['state'] == 'open':
                        matched_closed_alert_count += 1
                        if args.dry_run is False:
                            # Update destination alerts
                            logging.debug(f"Updating secret scanning alert for {destination_org}/{destination_repo}")
                            destination_alert_url = f"{GITHUB_API_URL}/repos/{destination_org}/{destination_repo}/secret-scanning/alerts/{destination_alert['number']}"
                            new_comment = f"{source_alerts_dict[key]['resolved_by']['login']} closed alert at {source_alerts_dict[key]['resolved_at']} with the comment: '{source_alerts_dict[key]['resolution_comment']}'"
                            new_comment = new_comment[:280] # max comment length is 280 characters
                            update_secret_scanning_alert(destination_alert_url, destination_pat, source_alerts_dict[key]['state'], source_alerts_dict[key]['resolution'], new_comment)
    
    print(f"Total count of alerts mapped between source and destination repos: {matched_alert_count}")
    if args.dry_run is False:
        print(f"Count of alerts that were closed in the destination repos: {matched_closed_alert_count}")
    else:
        print(f"Count of alerts that would have been updated in the destination repos: {matched_closed_alert_count}")

if __name__ == '__main__':
    main()
