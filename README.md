# todoist-gsheet-export
Dumps out yesterdays completed tasks in Todoist and put them in a cell in a Google Sheet. Just a fun-hack-around-scratch-my-own-itch thing.

Reads yesterdays completed tasks from the Todoist API and then puts them (concatinated with ;) in a cell in a google sheet. A work log of sorts.

## Installationg
Currently very rudementry

```sh
pip install python-dotenv requests google-api-python-client google-auth
```

1. Get the API Key from Todoist
2. Go to the GCP Console
3. Create project (if needed) 
4. Enagle Google Sheets API
5. Create Service Account in the GCP project
6. Export the service accounts creds as JSON

Do a `cp .env.example .env` and update the `.env` file with the values aquired above.