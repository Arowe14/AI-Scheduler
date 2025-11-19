from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
from event import Event
import interpreter
import os
import json
from googleapiclient.errors import HttpError
from pathlib import Path
import copy

class Calendar:
    def __init__(self, service):
        """Initialize a Calendar instance with a Google Calendar service.
           Builds name-to-ID and ID-to-name mappings for calendars.
           Sets the primary timezone for the calendar."""
        self.service = service
        self.name_to_id, self.id_to_name = self._build_maps()
        self.timezone = self._get_primary_timezone()

    def _get_primary_timezone(self):
        """Fetch the primary calendar's timezone."""
        try:
            primary_cal = self.service.calendars().get(calendarId='primary').execute()
            return primary_cal.get('timeZone', 'America/Toronto')
        except Exception as e:
            print(f"Error fetching primary calendar timezone: {e}")
            return 'America/Toronto'

    def _build_maps(self):
        """Fetch all calendars and build name-to-ID and ID-to-name mappings."""
        calendars = self.service.calendarList().list().execute().get('items', [])
        name_to_id = {c['summary']: c['id'] for c in calendars}
        id_to_name = {c['id']: c['summary'] for c in calendars}
        return name_to_id, id_to_name

    def get_calendar_names(self):
        """Return a list of available calendar names."""
        return list(self.name_to_id.keys())

    def add_events(self, event_list):
        """Adds a list of events to the calendar."""

        for event in event_list:
            self._insert_event(event)
        
        print("All events added to calendar.")
        return event_list

    def _insert_event(self, event):
        """Add an Event instance to the appropriate calendar, with error handling."""
        calendar_id = self.name_to_id.get(event.calendar_name, 'primary')
        event_body = event.to_google_format(self.timezone)

        print(f"Event start: {event.start}, Type: {type(event.start)}")
        print(f"Event end: {event.end}, Type: {type(event.end)}")
        try:
            created_event = self.service.events().insert(
                calendarId=calendar_id,
                body=event_body
            ).execute()

            html_link = created_event.get('htmlLink', 'No link available')
            print(f"✅ Event created in '{event.calendar_name}': {html_link}")
            return created_event

        except HttpError as error:
            error_details = error.content.decode("utf-8") if hasattr(error, "content") else str(error)
            print(f"❌ Failed to create '{event.summary}' in '{event.calendar_name}': {error_details}")
            try:
                print("Event body sent to API:")
                print(json.dumps(event_body, indent=2))
            except Exception:
                pass
            return None

        except Exception as e:
            print(f"❌ Unexpected error while creating event in '{event.calendar_name}': {e}")
            return None

    def _remove_event(self, event):
        """
        Remove an event from the calendar by its ID.
        """
        calendar_id = self.name_to_id.get(event.calendar_name, 'primary')
        try:
            self.service.events().delete(
                calendarId=calendar_id,
                eventId=event.id
            ).execute()
            print(f"Event {event.id} deleted from {event.calendar_name}.")
        except Exception as e:
            print(f"Error deleting event {event.id}: {e}")

    def get_events(self, date):
        """
        Retrieve events for a specific date from all calendars.
        
        Google calendar provides
        - id (string): unique identifier for the event
        - summary (string): title or name of the event
        - start (datetime or date): Contains datetime or date object of the start of the event, depending on the event result
        - end (datetime or date): End of the event
        - description (string): optional detailed notes
        - location (string) physical or virtual location
        """
        if isinstance(date, str):
            date = datetime.fromisoformat(date).date()

        # Define time window for the day
        day_start = datetime.combine(date, time(0, 0, tzinfo=ZoneInfo(self.timezone)))
        day_end = datetime.combine(date, time(23, 59, tzinfo=ZoneInfo(self.timezone)))

        all_events = []

        for calendar_name, calendar_id in self.name_to_id.items():
            events_result = self.service.events().list(
                calendarId=calendar_id,
                timeMin=day_start.isoformat(),
                timeMax=day_end.isoformat(),
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            for event_data in events_result.get('items', []):
                start_info = event_data.get('start', {})
                end_info = event_data.get('end', {})

                event = Event(
                    id=event_data.get('id'),
                    summary=event_data.get('summary'),
                    start=start_info.get('dateTime') or start_info.get('date'),
                    end=end_info.get('dateTime') or end_info.get('date'),
                    description=event_data.get('description'),
                    location=event_data.get('location'),
                    calendar_name=calendar_name
                )
                event.duration = ((event.end - event.start).total_seconds() / 60) if event.start and event.end else 60
                all_events.append(event)

        return all_events
    
    def save_events(self, event_list, filename="events.json"):
        """
        Save events to a JSON file, merging with existing events if the file exists.
        Event duplicates are removed based on event ID, and days are kept sorted.

        Args:
            event_list (list[Event]): List of Event instances to save.
            filename (str): The name of the JSON file to save events to.
        """
        newly_added = []
        # Load existing events if the file exists
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                try:
                    existing_events = json.load(f)
                except json.JSONDecodeError:
                    existing_events = {}
        else:
            existing_events = {}
        
        # Ensure existing_events is a dict
        if not isinstance(existing_events, dict):
            existing_events = {}

        # Merge new events
        for event in event_list:
            # Grab event date, otherwise fallback to 'todo' bucket.
            event_date = event.date.isoformat() if event.start else 'todo'

            # Ensure the date key exists
            if event_date not in existing_events:
                existing_events[event_date] = []

            # Remove duplicates by event ID, then add the new one
            existing_events[event_date] = [
                e for e in existing_events[event_date]
                if not (
                    (event.id is not None and e.get('id') == event.id)
                    or (
                        e.get('summary') == event.summary
                        and (event.start and e.get('start') == event.start.isoformat())
                    )
                )
            ]
            newly_added.append(event)
        
        event_type = interpreter.determine_event_type(newly_added)
        for ev, ev_type in zip(newly_added, event_type):
            ev.event_type = ev_type
            existing_events[ev.date.isoformat()].append(ev.to_dict())

            # Sort events within the day by start time (None -> empty string)
            existing_events[ev.date.isoformat()].sort(key=lambda x: x['start'] or "")
        
        # Sort the days themselves
        existing_events = dict(sorted(existing_events.items()))

        # Save back to file
        with open(filename, 'w') as f:
            json.dump(existing_events, f, indent=4)

    def schedule_events(self, new_events, existing_events):
        """
        Schedule new events against an existing calendar.

        Parameters:
            new_events (list[Event]): Events being added (timed, chores, todos).
            existing_events (list[Event]): Events already scheduled in the calendar.
        Returns:
            scheduled_event_list (list[Event]): Updated list of all scheduled events.
            to_add (list[Event]): Events to be added.
            to_remove (list[Event]): Events to be removed (Old copies that were rescheduled).
        """
        scheduled_event_list = existing_events.copy()
        to_add = []
        to_remove = []
        # Separate new events into types
        timed_events = [e for e in new_events if e.event_type == 'timed']
        chores = [e for e in new_events if e.event_type == 'chore']
        todos = [e for e in new_events if e.event_type == 'todo']

        # Handle timed events first (may cause rescheduling of chores)
        for event in timed_events:
            to_remove.extend(copy.deepcopy(self._reschedule_conflicting_events(event)))
            scheduled_event_list.append(event)
            to_add.append(event)
        
        chores = to_remove + chores

        # Schedule chores
        for chore in chores:
            scheduled_chore = self._schedule_chore(chore, scheduled_event_list)
            scheduled_event_list.append(scheduled_chore)
            to_add.append(scheduled_chore)

        # Schedule todos
        for todo in todos:
            scheduled_todo = self._schedule_todo(todo, scheduled_event_list)
            scheduled_event_list.append(scheduled_todo)
            to_add.append(scheduled_todo)

        return scheduled_event_list, to_add, to_remove

    def _read_events(self, timed_start, timed_end, timed_date) -> list[Event]:
        """Read events from events.json for the given times.
        Returns a list of event objects within those times."""
        events = []

        events_path = Path("events.json")
        if not events_path.exists():
            print("events.json file not found.")
            return events

        with open(events_path, 'r', encoding="utf-8") as f:
            try:
                all_events = json.load(f)
            except json.JSONDecodeError:
                print("Error decoding events.json.")
                return events
            
        date_str = timed_date.isoformat()
        start_str = timed_start.isoformat()
        end_str = timed_end.isoformat()

        if date_str not in all_events:
            return events

        for event_data in all_events[date_str]:
            event_start = event_data.get('start')
            event_end = event_data.get('end')

            if event_end >= start_str or event_start <= end_str:
                events.append(Event.from_dict(event_data))

        return events

    def _schedule_chore(self, event, existing_events):
        """
        Schedule a chore (event with date but no time).
        Places the event in the first available time slot on the given date
        between 8 AM and 8 PM, avoiding conflicts with existing events.
        """

        date = event.date
        day_start = datetime.combine(date, time(8, 0, tzinfo=ZoneInfo(self.timezone)))
        day_end   = datetime.combine(date, time(20, 0, tzinfo=ZoneInfo(self.timezone)))

        # Collect busy times from existing events on the same date
        busy_times = []
        for e in existing_events:
            if e.date == date:
                busy_times.append({"start": e.start, "end": e.end})

        # Sort busy times by start time
        busy_times.sort(key=lambda b: b["start"])

        # Find the first available slot
        slot_start = day_start
        for busy in busy_times:
            busy_start, busy_end = busy["start"], busy["end"]

            # Check if there's enough time before the busy slot
            gap_minutes = (busy_start - slot_start).total_seconds() / 60

            if gap_minutes >= event.duration:
                event.start = slot_start
                event.end   = slot_start + timedelta(minutes=event.duration)
                return event

            # Move slot_start to the end of the busy period
            slot_start = max(slot_start, busy_end)

        # Check for a slot after the last busy period
        gap_minutes = (day_end - slot_start).total_seconds() / 60

        if gap_minutes >= event.duration:
            event.start = slot_start
            event.end   = slot_start + timedelta(minutes=event.duration)
            return event

        return None  # Return unscheduled if no slot found


    def _schedule_todo(self, event, event_list):
        """
        Schedule a todo task (Event with no date or time).
        Places the event within the next 7 days in the first available time slot between 8 AM and 8 PM.
        """
        for i in range(7):
            date = datetime.now() + timedelta(days=i)
            event.date = date.date()
            if self._schedule_chore(event, event_list):
                return event
        print(f"No available slot found for todo '{event.summary}' in the next 7 days.")
        return None

    def _reschedule_conflicting_events(self, timed_event):
        """
        Returns conflicting chores to be rescheduled.
        """
        conflicting_chores = []
        conflicting_events = self._read_events(timed_event.start, timed_event.end, timed_event.date)
        for event in conflicting_events:
            if event.event_type == 'chore':
                conflicting_chores.append(event)
        return conflicting_chores
