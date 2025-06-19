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

def get_day_iso_range(days_ago=1):
    """
    Returns the start and end datetime strings in ISO format (with Z suffix for UTC)
    for a given number of days ago.
    """
    # Get current UTC date and subtract the specified number of days.
    target_date = datetime.datetime.utcnow().date() - datetime.timedelta(days=days_ago)
    
    # Define the start (00:00:00) and end (23:59:59.999999) of the target day.
    start = datetime.datetime.combine(target_date, datetime.time.min).isoformat() + 'Z'
    end = datetime.datetime.combine(target_date, datetime.time.max).isoformat() + 'Z'
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

def update_google_sheet_cell(value_to_insert, cell_name):
    """
    Updates a specific cell in the Google Sheet with the given value.
    """
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    credentials = Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=scopes
    )
    service = build('sheets', 'v4', credentials=credentials)
    
    body = {"values": [[value_to_insert]]}
    result = service.spreadsheets().values().update(
        spreadsheetId=GOOGLE_SHEET_ID,
        range=cell_name,
        valueInputOption="RAW",         # write the data as-is
        body=body
    ).execute()
    
    updated_cells = result.get("updatedCells", 0)
    print(f"Successfully updated {updated_cells} cells in the Google Sheet.")

def get_cell_value(cell_name):
    """
    Retrieves the value of a specific cell from the Google Sheet.
    """
    scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
    credentials = Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=scopes
    )
    service = build('sheets', 'v4', credentials=credentials)
    
    # Get the values from the specified tab in the Google Sheet.
    result = service.spreadsheets().values().get(
        spreadsheetId=GOOGLE_SHEET_ID,
        range=cell_name
    ).execute()
    
    values = result.get("values", [])
    if not values or not values[0]:
        return None
    return values[0][0]

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

    # Todoist - get project id for the specified project name
    project_id = get_project_id(TODOIST_PROJECT_NAME)

    for days_ago in range(1, 8):
        # Determine the ISO date range for the specific day
        start_iso, end_iso = get_day_iso_range(days_ago)
        print(f"Checking for tasks completed on {start_iso[:10]}")

        # Google Sheets - Get the tab name for the month of the date we are checking
        short_year, short_month, iso_date = split_date_string(start_iso)
        current_tab_name = get_tab_name(short_year, short_month)
        tabs_in_sheet = list_sheet_tabs()

        # Verify that tab exists in the Google Sheet
        if current_tab_name not in tabs_in_sheet:
            print(f"Tab '{current_tab_name}' not found in the Google Sheet. Skipping.")
            continue

        # Find the row for the date
        rows = get_rows_from_google_sheet(current_tab_name)
        row_index = -1
        for i, row in enumerate(rows):
            if len(row) > 0 and row[0] == iso_date:
                row_index = i + 1
                break

        if row_index == -1:
            print(f"Date {iso_date} not found in sheet '{current_tab_name}'. Skipping.")
            continue

        cell_to_check = f"{current_tab_name}!E{row_index}"

        # Check if cell is empty
        cell_value = get_cell_value(cell_to_check)

        if cell_value:
            print(f"Cell {cell_to_check} already has data: '{cell_value}'. Exiting.")
            break

        # Cell is empty, get tasks from Todoist
        print(f"Cell {cell_to_check} is empty. Fetching tasks from Todoist.")
        tasks = get_completed_tasks(start_iso, end_iso, project_id)

        string_to_insert = ""
        if not tasks:
            print(f"No completed tasks found for {iso_date}.")
            string_to_insert = "N/A"
        else:
            task_contents = [task.get("content", "") for task in tasks]
            string_to_insert = "; ".join(task_contents)
            for task_name in task_contents:
                print(f"  ->  Task: {task_name}")

        print(f"\n--------\nInserting the following into cell {cell_to_check}\n--------\n")
        update_google_sheet_cell(string_to_insert, cell_to_check)


if __name__ == "__main__":
    main()
