from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

class Event:
    def __init__(self, summary, _date=None, start=None, end=None,**kwargs):
        self.id = kwargs.get('id', None)
        self.summary = summary
        self.date = _date

        # Normalize start
        if isinstance(start, str):
            self.start = datetime.fromisoformat(start)
        else:
            self.start = start
        if self.start and self.start.tzinfo is None:
            self.start = self.start.replace(tzinfo=kwargs.get('timezone'))

        # Normalize end
        if isinstance(end, str):
            self.end = datetime.fromisoformat(end)
        else:
            self.end = end
        if self.end and self.end.tzinfo is None:
            self.end = self.end.replace(tzinfo=kwargs.get('timezone'))

        self.duration = kwargs.get('duration', 60)
        if self.date is None and self.start:
            self.date = self.start.date()

        self.location = kwargs.get('location', '')
        self.description = kwargs.get('description', '')
        self.calendar_name = kwargs.get('calendar_name', 'primary')
        self.event_type = kwargs.get('event_type', None)


    @classmethod
    def from_dict(cls, data, timezone=ZoneInfo('America/Toronto')):
        """Create an Event instance from a dictionary (ignores event_type correctness)."""
        start_time = None
        end_time = None

        # Parse start time
        start_val = data.get('start')
        if start_val and 'T' in start_val:
            start_time = datetime.fromisoformat(start_val)
            if timezone:
                if start_time.tzinfo is None:
                    start_time = start_time.replace(tzinfo=timezone)
                else:
                    start_time = start_time.astimezone(timezone)

        # Parse end time
        end_val = data.get('end')
        if end_val and 'T' in end_val:
            end_time = datetime.fromisoformat(end_val)
            if timezone:
                if end_time.tzinfo is None:
                    end_time = end_time.replace(tzinfo=timezone)
                else:
                    end_time = end_time.astimezone(timezone)

        return cls(
            summary=data.get('summary'),
            date=data.get('date'),
            start=start_time,
            end=end_time,
            duration=data.get('duration', 60),
            location=data.get('location'),
            description=data.get('description'),
            calendar_name=data.get('calendarName', 'primary'),
            event_type=data.get('eventType'),
            id=data.get('id')
        )


    def to_dict(self):
        """Convert the Event instance to a dictionary."""
        return {
            'id': self.id,
            'summary': self.summary,
            'date': self.date.isoformat() if self.date else None,
            'start': self.start.isoformat() if self.start else None,
            'end': self.end.isoformat() if self.end else None,
            'duration': self.duration,
            'location': self.location,
            'description': self.description,
            'calendarName': self.calendar_name,
            'eventType': self.event_type
        }

    def to_google_format(self, timezone='America/Toronto'):
        """Convert the Event instance to Google Calendar API format (timed events only)."""
        event = {
            'summary': self.summary,
            'location': self.location,
            'description': self.description,
            'start': {
                'dateTime': self.start.isoformat() if self.start else None,
                'timeZone': timezone,
            },
            'end': {
                'dateTime': self.end.isoformat() if self.end else None,
                'timeZone': timezone,
            },
        }
        return event
    
