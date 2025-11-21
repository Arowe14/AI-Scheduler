from openai import OpenAI
import os
import json
import re
from event import Event
from datetime import datetime, date, time, timedelta
from dotenv import load_dotenv
from dateparser.search import search_dates


load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
now = datetime.now()
today = now.date()

def parse_date(text: str) -> date | None:
    results = search_dates(text, settings={"RELATIVE_BASE": now, "PREFER_DATES_FROM": "future"})
    if results:
        # returns list of tuples [(matched_text, datetime_obj)]
        _, dt = results[0]
        return dt.date()
    return None


def clean_json(content: str) -> str:
    return re.sub(r"^```(?:json)?\n|\n```$", "", content.strip())


def interpret_input(calendar_names: list[str], text: str) -> Event:
    prompt = f"""
You are an event interpreter. Today's date is {today}. 
Extract structured calendar event details from natural language.

Rules:
- Resolve relative dates like "tomorrow", "next Monday", "Saturday" using today's date ({today}).
- Each date mentioned should be after or on today's date.
- For example, "Tomorrow" means {today + timedelta(days=1)}, "Monday" means the next occurrence of Monday from today, but "next Monday" means the Monday after the upcoming one.
- If only a date is mentioned (e.g., "on Saturday"), set time fields to null.
- If only a time is mentioned (e.g., "at 1"), assume it refers to today's date unless another date is specified.
- If a time is mentioned without AM/PM, infer from context (e.g., "Lunch at 1" → 13:00).
- If no date or time is mentioned, set those fields to null.

Input: "{text}"

Return a JSON object with these keys:
- summary (string): title of the event
- date (string in YYYY-MM-DD format): the event date, or null if not mentioned
- start (string in YYYY-MM-DDTHH:MM:SS format): the event start time, or null if not mentioned
- duration (int): the event duration in minutes, or an estimate if not mentioned
- location (string): the event location, or an expected location if not mentioned, for example "Doctor's office" for a doctor's appointment
- description (string): a short description of the event
- calendarName (string): choose the most appropriate calendar from this list: {calendar_names}

Respond with only the JSON object.
"""

    response = client.chat.completions.create(
        model="gpt-4.1",
        messages=[{"role": "user", "content": prompt}]
    )
    content = response.choices[0].message.content
    if content is None:
        raise ValueError("OpenAI API returned None content")
    content = content.strip()

    cleaned = clean_json(content)
    event_data = json.loads(cleaned)

    event = Event.from_dict(event_data)
    if not event.date:
        event.date = parse_date(text)

    if event.duration==None:
        if event.start and event.end:
            delta = event.end - event.start
            event.duration = int(delta.total_seconds() // 60)
        else:
            event.duration = 60  # default duration

    event.end = event.start + timedelta(minutes=event.duration) if event.start else None
    if event.start:
        event.event_type = 'timed'
    elif event.date:
        event.event_type = 'chore'
    else:
        event.event_type = 'todo'
    return event


def determine_event_type(events) -> list[str]:
    event_details = [e.description or e.summary for e in events]
    events_text = "\n".join(event_details)

    prompt = f"""
You are an event classifier. Given the following event titles, classify each as 'timed', 'chore', or 'todo'.
Rules:
- 'timed': an event with a specific start and end time (e.g., Work meetings, appointments).
- 'chore': an event with no specific time (e.g., grocery shopping, cleaning).


Events: {events_text}

Respond with a list of classifications corresponding to each event, in order. Only respond with a single word for each classification.
Example response:
timed, chore, todo, timed, todo
"""

    response = client.chat.completions.create(
        model="gpt-4.1",
        messages=[{"role": "user", "content": prompt}]
    )
    content = response.choices[0].message.content
    if content is None:
        raise ValueError("OpenAI API returned None content")
    content = content.strip()

    classifications = [c.strip().lower() for c in content.split(",")]
    return classifications