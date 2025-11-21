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

        try:
            created_event = self.service.events().insert(
                calendarId=calendar_id,
                body=event_body
            ).execute()

            html_link = created_event.get('htmlLink', 'No link available')
            return created_event

        except HttpError as error:
            error_details = error.content.decode("utf-8") if hasattr(error, "content") else str(error)
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
        exist_length = len(existing_events)

        for e in scheduled_event_list:
            print("Existing event: ", e.summary, e.event_type)
        to_add = []
        to_remove = []
        # Separate new events into types
        timed_events = [e for e in new_events if e.event_type == 'timed']
        chores = [e for e in new_events if e.event_type == 'chore']
        todos = [e for e in new_events if e.event_type == 'todo']
        print("Final scheduled events amount 0: ", len(scheduled_event_list))
        # Handle timed events first (may cause rescheduling of chores)
        for event in timed_events:
            conflict = self._find_conflicting_events(event)
            if conflict:
                for c in conflict:
                    print("Conflicting event found:", c.summary, c.event_type)
                    if c.event_type == 'chore':
                        print(f"Rescheduling chore '{c.summary}' due to conflict with timed event '{event.summary}'.")
                        # Remove by ID instead of object identity
                        scheduled_event_list = [e for e in scheduled_event_list if e.id != c.id]
                        to_remove.append(c)
                        chores.append(c)
                    else:
                        print(f"Timed event '{event.summary}' conflicts with another timed event; not rescheduling.")

            to_add.append(event)
        print("Final scheduled events amount 1: ", len(scheduled_event_list))

        # Schedule chores
        for chore in chores:
            scheduled_chore = self._schedule_chore(chore, scheduled_event_list)
            to_add.append(scheduled_chore)
        print("Final scheduled events amount 2: ", len(scheduled_event_list))
        # Schedule todos
        for todo in todos:
            scheduled_todo = self._schedule_todo(todo, scheduled_event_list)
            to_add.append(scheduled_todo)
        print("Final scheduled events amount 3: ", len(scheduled_event_list))
        return scheduled_event_list, to_add, to_remove

    def _read_events(self, timed_start, timed_end) -> list[Event]:
        """
        Read events from events.json that overlap the given time window.
        Returns a list of Event objects.
        """
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

        # Collect all date keys that fall within the time window
        current_date = timed_start.date()
        end_date = timed_end.date()
        date_keys = []
        while current_date <= end_date:
            date_keys.append(current_date.isoformat())
            current_date += timedelta(days=1)

        # Only iterate over relevant date buckets
        for date_key in date_keys:
            if date_key not in all_events:
                continue

            for event_data in all_events[date_key]:
                if not isinstance(event_data, dict):
                    print("Skipping malformed event:", event_data)
                    continue

                print("Event: ", event_data.get('summary'), event_data.get('eventType'))
                event = Event.from_dict(event_data, timezone=ZoneInfo(self.timezone))
                print("Loaded event:", event.summary, "Type:", event.event_type)

                # Only include if event overlaps the time window
                if event.start and event.end:
                    if event.start < timed_end and event.end > timed_start:
                        events.append(event)

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


        for b in busy_times:
            print("Busy:", b["start"], b["start"].tzinfo)

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

        return event  # Return unscheduled if no slot found


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
        return event

    def _find_conflicting_events(self, timed_event):
        """
        Returns conflicting chores to be rescheduled.
        """
        start = timed_event.start.astimezone(ZoneInfo(self.timezone))
        end = timed_event.end.astimezone(ZoneInfo(self.timezone))

        conflicting_events = self._read_events(start, end)
        for event in conflicting_events:
            print(f"Found conflicting event: {event.summary} ({event.start} - {event.end}), type: {event.event_type}")
        return conflicting_events
