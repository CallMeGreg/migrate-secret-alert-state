# Overview
This script ([main.py](./main.py)) migrates the state of GitHub Advanced Security secret scanning alerts from GitHub Enterprise Server (GHES) repositories to GitHub Enterprise Cloud (GHEC) repositories. The actor, reason, comment, and timestamp from the source repository alert will be captured in the destination repository alert.

# Pre-requisites
- Python 3
- Python `requests` library (install using `pip install requests`)
- A CSV file with four columns: `Source Org`, `Source Repo`, `Destination Org`, and `Destination Repo` (see [example.csv](./example.csv)).
  - The script will read the CSV file row by row and migrate the secret scanning alert states from the source org/repo to the destination org/repo.
- A Personal Access Token (PAT) from each enterprise with the following scopes:
  - `repo` (Full control of private repositories)

# Assumptions
- The Source and Destination PATs have access to ALL GHES and GHEC secret scanning alerts respectively (Note: Enterprise Owners do NOT have access to all alerts by default).
- GitHub Advanced Security, and secret scanning, are enabled on both the source and destination repositories.
- All custom patterns at the repository, organization, and enterprise level have identical names and patterns in both the source and destination repositories.
- If the alert state in the destination repository is already `resolved`, the script will NOT update the alert.
- The actor closing the destination alerts will be the user associated with the Destination PAT.

# Usage
## Setup
Set the following environment variables based on your GHES URL
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
By default, the script will run in dry-run mode. This will print the source and destination repository alert ID mappings without making any changes to the alerts, and list the number of mapped alerts in addition to the number of alerts that _would have been updated_. To run the script in dry-run mode, use the following command:
```
python3 main.py --csv path/to/your/example.csv
```

## Migration mode
When you're ready to migrate the alert states from the source to the destination repositories, you can disable dry-run mode by using the following command:
```
python3 main.py --csv path/to/your/example.csv --dry-run false
```