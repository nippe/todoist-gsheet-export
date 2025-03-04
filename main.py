import httpx
import datetime
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import os
from dotenv import load_dotenv


# --------------------------
# CONFIGURATION
# --------------------------
load_dotenv()

# Replace these with your own values:
TODOIST_API_TOKEN = os.getenv("TODOIST_API_TOKEN")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID" )
SERVICE_ACCOUNT_FILE = os.path.join(os.getcwd(), os.getenv("SERVICE_ACCOUNT_FILE"))
TODOIST_PROJECT_NAME = os.getenv("TODOIST_PROJECT_NAME")

TODOIST_GET_PROJECTS_URL = "https://api.todoist.com/rest/v2/projects"
TODOIST_GET_ALL_COMPLETED_URL = "https://api.todoist.com/sync/v9/completed/get_all"

# --------------------------
# FUNCTIONS
# --------------------------

def get_yesterday_iso_range():
    """
    Returns the start and end datetime strings in ISO format (with Z suffix for UTC)
    for yesterday.
    """
    # Get current UTC date and subtract one day for yesterday.
    today = datetime.datetime.utcnow().date()
    yesterday = today - datetime.timedelta(days=1)
    
    # Define the start (00:00:00) and end (23:59:59.999999) of yesterday.
    start = datetime.datetime.combine(yesterday, datetime.time.min).isoformat() + 'Z'
    end = datetime.datetime.combine(yesterday, datetime.time.max).isoformat() + 'Z'
    return start, end

def get_project_id(project_name):
    """
    Calls the Todoist API to get all projects.
    Returns a list of projects.
    """
    url = TODOIST_GET_PROJECTS_URL
    headers = {
        "Authorization": f"Bearer {TODOIST_API_TOKEN}"  # use your own API token
    }

    response = httpx.get(url, headers=headers)
    response.raise_for_status()  # will raise an error if the request failed
    projects = response.json()

    for project in projects:
        if project['name'] == project_name:
            return project['id']
    
    raise ValueError(f"Project '{project_name}' not found.")

def get_completed_tasks(start_iso, end_iso, project_id = "1233330094"):
    """
    Calls the Todoist API to get all completed tasks between the specified times.
    Returns a list of tasks.
    """
    url = TODOIST_GET_ALL_COMPLETED_URL
    headers = {
        "Authorization": f"Bearer {TODOIST_API_TOKEN}"
    }
    params = {
        "since": start_iso,  # start datetime for filtering completed tasks
        "until": end_iso,    # end datetime for filtering completed tasks
        "limit": 100,         # adjust the limit if you expect more tasks
        "project_id": project_id       # filter by project ID; set to 0 for all projects 
    }

    response = httpx.get(url, headers=headers, params=params)
    response.raise_for_status()  # will raise an error if the request failed
    data = response.json()
    
    # The returned JSON contains an 'items' key with the list of tasks.
    return data.get("items", [])

def write_to_google_sheet(value_to_insert, cell_name):
    """
    Appends the given value_to_insert to the Google Sheet.
    """
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    credentials = Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=scopes
    )
    service = build('sheets', 'v4', credentials=credentials)
    
    body = {"values": [[value_to_insert]]}
    result = service.spreadsheets().values().append(
        spreadsheetId=GOOGLE_SHEET_ID,
        range=cell_name,
        valueInputOption="RAW",         # write the data as-is
        body=body
    ).execute()
    
    updated_cells = result.get("updates", {}).get("updatedCells", 0)
    print(f"Successfully appended {updated_cells} cells to the Google Sheet.")

def list_sheet_tabs():
    """
    Retrieves all the tab names from the specified Google Sheet.
    """
    scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
    credentials = Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=scopes
    )
    service = build('sheets', 'v4', credentials=credentials)
    
    # Get the spreadsheet metadata, which includes the sheet (tab) info.
    spreadsheet = service.spreadsheets().get(
        spreadsheetId=GOOGLE_SHEET_ID
    ).execute()
    
    sheets = spreadsheet.get('sheets', [])
    sheet_titles = [sheet.get("properties", {}).get("title") for sheet in sheets]
    return sheet_titles

def get_rows_from_google_sheet(tab_name):
    """
    Retrieves all the rows from the specified tab in the Google Sheet.
    """
    scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
    credentials = Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=scopes
    )
    service = build('sheets', 'v4', credentials=credentials)
    
    # Get the values from the specified tab in the Google Sheet.
    result = service.spreadsheets().values().get(
        spreadsheetId=GOOGLE_SHEET_ID,
        range=f"{tab_name}!A1:Z"
    ).execute()
    # print(result)
    values = result.get("values", [])
    return values

def get_tab_name(year, month):
    """
    Generates a tab name based on the given year and month.
    """
    month_dict = {
        "01": "Jan",
        "02": "Feb",
        "03": "Mar",
        "04": "Apr",
        "05": "May",
        "06": "Jun",
        "07": "Jul",
        "08": "Aug",
        "09": "Sep",
        "10": "Oct",
        "11": "Nov",
        "12": "Dec"
    }

    return f"{month_dict[month]}-{year}"

def split_date_string(date_iso_string):
    """
    Splits the date string in ISO format and returns the year and month.
    """
    short_year = date_iso_string[2:4]
    short_month = date_iso_string[5:7]
    short_iso_date = date_iso_string[:10]
    return short_year, short_month, short_iso_date

# --------------------------
# MAIN EXECUTION
# --------------------------

def main():

    # Determine the ISO date range for yesterday
    start_iso, end_iso = get_yesterday_iso_range()
    print(f"Fetching tasks completed between {start_iso} and {end_iso}.")

    # Todoist - get project id for the specified project name
    project_id = get_project_id(TODOIST_PROJECT_NAME)

    # Todoist - Get the list of completed tasks from Todoist
    tasks = get_completed_tasks(start_iso, end_iso, project_id)
    
    if not tasks:
        print("No completed tasks found for yesterday.")
        return
    
    # Google Sheets - Get the tab name for the current month
    short_year, short_month, iso_date = split_date_string(start_iso)
    current_tab_name = get_tab_name(short_year, short_month)
    tabs_in_sheet = list_sheet_tabs()

      # Verify that tab exists in the Google Sheet
    if current_tab_name not in tabs_in_sheet:
        print(f"Tab '{current_tab_name}' not found in the Google Sheet.")
        return

    rows = get_rows_from_google_sheet(current_tab_name)

    i = 1
    for row in rows:
        if len(row) > 0:
            if  row[0] == iso_date:
                print(f"Found the row: {i} - {row=}")
                break
        i += 1

    cell_name = f"{current_tab_name}!E{i}"

    string_to_insert = ""
    for task in tasks:
        task_name = task.get("content", "")
        string_to_insert += task_name + "; "
        print(f"  ->  Task: {task_name}")

    print(f"\n--------\nInserting the following tasks into cell {cell_name}\n--------\n")
    write_to_google_sheet(string_to_insert, cell_name)

if __name__ == "__main__":
    main()
