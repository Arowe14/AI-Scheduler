# Imports
from __future__ import print_function
from googleapiclient.discovery import build
from calendar_class import Calendar
from event import Event
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from zoneinfo import ZoneInfo
import datetime
import interpreter
import interface
import os.path
import json



# If modifying scopes, delete the token.json file.
SCOPES = ['https://www.googleapis.com/auth/calendar']

def credentials():
        # token.json stores the user's access/refresh tokens
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    # If no valid credentials, log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save credentials for next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return creds

def load_from_json(filename="test_events.json"):
    """Load events from JSON file."""
    with open(filename, 'r') as f:
        data = json.load(f)

    events = []
    for date_str, day_events in data.items():
        for e in day_events:
            event = Event.from_dict(e)
            events.append(event)

    return events

def clear_json(filename="events.json"):
    """Clear the contents of the JSON file."""
    with open(filename, 'w') as f:
        json.dump({}, f)


def main():
    today = datetime.date.today()
    creds = credentials()
    service = build('calendar', 'v3', credentials=creds)
    

    calendar = Calendar(service)

    event_list = []
    


    interface.run_interface(calendar)
    calendar.save_events(event_list, filename="events.json")
    clear_json(filename="events.json")
if __name__ == '__main__':
    main()