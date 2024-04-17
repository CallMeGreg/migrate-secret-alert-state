# Overview
This script ([main.py](./main.py)) migrates the state of GitHub Advanced Security secret scanning alerts from GitHub Enterprise Server (GHES) repositories to GitHub Enterprise Cloud (GHEC) repositories.

# How it works
The script works by looking at a CSV file to determine which GHES source orgs/repos map to which GHEC destination orgs/repos. For each repo pair, the script confirms that secret scanning is enabled in both repos, and looks at both the _pattern name_ and _secret value_ to match a source alert ID to a destination alert ID.

If the source alert state is `resolved`, and the destination alert state is `open`, the script will close the destination alert using the same reason. The comment attached to the destination alert will include the source alert actor, timestamp of resolution, and comment.

# Pre-requisites
- Python 3
- Python `requests` library (install using `pip install requests`)
- A CSV file that maps source repos to destination repos with four columns: `Source Org`, `Source Repo`, `Destination Org`, and `Destination Repo` (see [example.csv](./example.csv)).
- A GitHub Personal Access Token (PAT) from each enterprise with the following scope:
  - `repo` (Full control of private repositories)

# Assumptions
- The source and destination PATs have access to ALL GHES and GHEC secret scanning alerts respectively (Note: Enterprise Owners do NOT have access to all alerts by default).
- GitHub Advanced Security, and secret scanning, are enabled on both the source and destination repositories.
- The secret scanning backfill scan has completed in the destination repository.
- All custom patterns at the repository, organization, and enterprise level have identical names and patterns in both the source and destination enterprises.
- If the alert state in the destination repository is already `resolved`, the script will NOT update the alert.
- The actor closing the destination alerts will be the user associated with the destination PAT (although the comment will contain the actor who closed the source alert).

# Usage
## Setup
Set the following environment variables, replacing the values with your GHES API URL, Source PAT, and Desination PAT.
```
export SOURCE_API_URL=<https://your.ghes.server.com/api/v3>
```
```
export SOURCE_PAT=<ghes_pat>
```
```
export DESTINATION_PAT=<ghec_pat>
```

## Dry run mode
By default, the script will run in dry-run mode. This will log the source and destination repository alert ID mappings without making any changes to the alerts, and list the number of mapped alerts in addition to the number of alerts that _would have been updated_. To run the script in dry-run mode, use the following command:
```
python3 main.py --csv path/to/your/example.csv
```

## Migration mode
When you're ready to migrate the alert states from the source to the destination repositories, you can disable dry-run mode by using the following command:
```
python3 main.py --csv path/to/your/example.csv --dry-run false
```

# Example
The following screenshots show the audit trail of an example source and destination alert after running the state migration script:

## Source Alert
![Screenshot 2024-04-17 at 5 06 27 PM](https://github.com/CallMeGreg/migrate-secret-alert-state/assets/110078080/95a63043-1de1-4ca6-81dc-8a5dc2354b15)

## Destination Alert
![Screenshot 2024-04-17 at 5 17 53 PM](https://github.com/CallMeGreg/migrate-secret-alert-state/assets/110078080/982ba65f-2a97-434d-95bd-2a6bf92ded7a)
