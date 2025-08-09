import httpx
import datetime
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import os
from dotenv import load_dotenv
import time
import logging
from typing import Optional, List


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
# CONFIGURATION VALIDATION
# --------------------------

def validate_configuration():
    """
    Validate that all required configuration is present.
    """
    required_vars = {
        "TODOIST_API_TOKEN": TODOIST_API_TOKEN,
        "GOOGLE_SHEET_ID": GOOGLE_SHEET_ID,
        "SERVICE_ACCOUNT_FILE": SERVICE_ACCOUNT_FILE,
        "TODOIST_PROJECT_NAME": TODOIST_PROJECT_NAME
    }
    
    missing_vars = [var for var, value in required_vars.items() if not value]
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
    
    # Check if service account file exists
    if not os.path.exists(SERVICE_ACCOUNT_FILE):
        raise FileNotFoundError(f"Service account file not found: {SERVICE_ACCOUNT_FILE}")
    
    print("Configuration validation passed.")

# --------------------------
# GOOGLE SHEETS SERVICE
# --------------------------

def get_google_sheets_service():
    """
    Create and return a Google Sheets service instance.
    """
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    try:
        credentials = Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=scopes
        )
        service = build('sheets', 'v4', credentials=credentials)
        return service
    except Exception as e:
        raise Exception(f"Failed to create Google Sheets service: {str(e)}")

# --------------------------
# API RETRY LOGIC
# --------------------------

def retry_api_call(func, max_retries=3, delay=1):
    """
    Retry an API call with exponential backoff.
    """
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            print(f"API call failed (attempt {attempt + 1}/{max_retries}): {str(e)}")
            time.sleep(delay * (2 ** attempt))  # Exponential backoff
    
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
    Returns the project ID for the specified project name.
    """
    def _make_request():
        url = TODOIST_GET_PROJECTS_URL
        headers = {
            "Authorization": f"Bearer {TODOIST_API_TOKEN}"
        }
        response = httpx.get(url, headers=headers)
        response.raise_for_status()
        return response.json()
    
    try:
        projects = retry_api_call(_make_request)
        for project in projects:
            if project['name'] == project_name:
                return project['id']
        raise ValueError(f"Project '{project_name}' not found.")
    except Exception as e:
        raise Exception(f"Failed to get project ID: {str(e)}")

def get_completed_tasks(start_iso, end_iso, project_id):
    """
    Calls the Todoist API to get all completed tasks between the specified times.
    Returns a list of tasks.
    """
    def _make_request():
        url = TODOIST_GET_ALL_COMPLETED_URL
        headers = {
            "Authorization": f"Bearer {TODOIST_API_TOKEN}"
        }
        params = {
            "since": start_iso,
            "until": end_iso,
            "limit": 100,
            "project_id": project_id
        }
        response = httpx.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()
    
    try:
        data = retry_api_call(_make_request)
        return data.get("items", [])
    except Exception as e:
        raise Exception(f"Failed to get completed tasks: {str(e)}")

def update_google_sheet_cell(service, value_to_insert, cell_name):
    """
    Updates a specific cell in the Google Sheet with the given value.
    """
    def _make_request():
        body = {"values": [[value_to_insert]]}
        result = service.spreadsheets().values().update(
            spreadsheetId=GOOGLE_SHEET_ID,
            range=cell_name,
            valueInputOption="RAW",
            body=body
        ).execute()
        return result
    
    try:
        result = retry_api_call(_make_request)
        updated_cells = result.get("updatedCells", 0)
        print(f"Successfully updated {updated_cells} cells in the Google Sheet.")
    except Exception as e:
        raise Exception(f"Failed to update Google Sheet cell {cell_name}: {str(e)}")

def get_cell_value(service, cell_name):
    """
    Retrieves the value of a specific cell from the Google Sheet.
    """
    def _make_request():
        result = service.spreadsheets().values().get(
            spreadsheetId=GOOGLE_SHEET_ID,
            range=cell_name
        ).execute()
        return result
    
    try:
        result = retry_api_call(_make_request)
        values = result.get("values", [])
        if not values or not values[0]:
            return None
        return values[0][0]
    except Exception as e:
        raise Exception(f"Failed to get cell value from {cell_name}: {str(e)}")

def list_sheet_tabs(service):
    """
    Retrieves all the tab names from the specified Google Sheet.
    """
    def _make_request():
        spreadsheet = service.spreadsheets().get(
            spreadsheetId=GOOGLE_SHEET_ID
        ).execute()
        return spreadsheet
    
    try:
        spreadsheet = retry_api_call(_make_request)
        sheets = spreadsheet.get('sheets', [])
        sheet_titles = [sheet.get("properties", {}).get("title") for sheet in sheets]
        return sheet_titles
    except Exception as e:
        raise Exception(f"Failed to list sheet tabs: {str(e)}")

def get_rows_from_google_sheet(service, tab_name):
    """
    Retrieves all the rows from the specified tab in the Google Sheet.
    """
    def _make_request():
        result = service.spreadsheets().values().get(
            spreadsheetId=GOOGLE_SHEET_ID,
            range=f"{tab_name}!A1:Z"
        ).execute()
        return result
    
    try:
        result = retry_api_call(_make_request)
        values = result.get("values", [])
        return values
    except Exception as e:
        raise Exception(f"Failed to get rows from sheet tab {tab_name}: {str(e)}")

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
    try:
        # Validate configuration before starting
        validate_configuration()
        
        # Create Google Sheets service once
        print("Initializing Google Sheets service...")
        sheets_service = get_google_sheets_service()
        
        # Todoist - get project id for the specified project name
        print(f"Getting project ID for '{TODOIST_PROJECT_NAME}'...")
        project_id = get_project_id(TODOIST_PROJECT_NAME)
        print(f"Project ID: {project_id}")

        for days_ago in range(1, 8):
            try:
                # Determine the ISO date range for the specific day
                start_iso, end_iso = get_day_iso_range(days_ago)
                print(f"Checking for tasks completed on {start_iso[:10]}")

                # Google Sheets - Get the tab name for the month of the date we are checking
                short_year, short_month, iso_date = split_date_string(start_iso)
                current_tab_name = get_tab_name(short_year, short_month)
                tabs_in_sheet = list_sheet_tabs(sheets_service)

                # Verify that tab exists in the Google Sheet
                if current_tab_name not in tabs_in_sheet:
                    print(f"Tab '{current_tab_name}' not found in the Google Sheet. Skipping.")
                    continue

                # Find the row for the date
                rows = get_rows_from_google_sheet(sheets_service, current_tab_name)
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
                cell_value = get_cell_value(sheets_service, cell_to_check)

                if cell_value:
                    print(f"Cell {cell_to_check} already has data: '{cell_value}'. Skipping.")
                    continue

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
                update_google_sheet_cell(sheets_service, string_to_insert, cell_to_check)
                
            except Exception as e:
                print(f"Error processing day {days_ago}: {str(e)}")
                continue
                
        print("\nTask processing completed successfully!")
        
    except Exception as e:
        print(f"Fatal error: {str(e)}")
        return 1
    
    return 0


if __name__ == "__main__":
    main()
