from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

class Event:
    def __init__(self, summary, _date=None, start=None, end=None, **kwargs):
        """
        Initialize an Event instance.
        event_type can be 'timed', 'chore', or 'todo'.
        """
        self.id = kwargs.get('id', None)
        self.summary = summary
        self.date = _date
        self.start = datetime.fromisoformat(start) if isinstance(start, str) else start
        self.duration = kwargs.get('duration', 60)  # in minutes
        self.end = datetime.fromisoformat(end) if isinstance(end, str) else end
        if self.date==None and self.start:
            self.date=self.start.date()

        self.location = kwargs.get('location', '')
        self.description = kwargs.get('description', '')
        self.calendar_name = kwargs.get('calendar_name', 'primary')
        self.event_type = kwargs.get('event_type', None)

    def _infer_event_type(self):
        """Infer event type based on provided attributes."""
        if self.start and self.end:
            self.event_type = 'timed'
        elif self.date:
            self.event_type = 'chore'
        else:
            self.event_type = 'todo'


    @classmethod
    def from_dict(cls, data):
        """Create an Event instance from a dictionary."""
        start_time = None
        end_time = None

        if data.get('start'):
            if 'T' in data.get('start'):
                start_time = datetime.fromisoformat(data.get('start'))
        if data.get('end'):
            if 'T' in data.get('end'):
                end_time = datetime.fromisoformat(data.get('end'))

        return cls(
            summary=data.get('summary'),
            date=data.get('date'),
            start=start_time,
            end=end_time,
            duration=data.get('duration', 60),
            location=data.get('location'),
            description=data.get('description'),
            calendar_name=data.get('calendarName', 'primary'),
            event_type=data.get('event_type'),
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