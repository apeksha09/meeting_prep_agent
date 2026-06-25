"""
Meeting Prep Agent
Reads meetings/, people/, and emails/ data, generates a pre-meeting briefing via Claude.
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
import anthropic
from dotenv import load_dotenv

load_dotenv()

# Fix Windows terminal encoding
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).parent
MEETINGS_DIR = BASE_DIR / "meetings"
PEOPLE_DIR = BASE_DIR / "people"
EMAILS_DIR = BASE_DIR / "emails"

MY_PERSON_ID = "p1"
MINUTES_AHEAD = 12000


def load_all(directory: Path) -> dict:
    records = {}
    for f in sorted(directory.glob("*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        records[data["id"]] = data
    return records


def get_upcoming_meetings(meetings: dict, now: datetime, window_minutes: int) -> list:
    upcoming = []
    cutoff = now + timedelta(minutes=window_minutes)
    for mtg in meetings.values():
        if "start" not in mtg:
            continue
        start = datetime.fromisoformat(mtg["start"])
        if now <= start <= cutoff and MY_PERSON_ID in mtg.get("people_involved", []):
            upcoming.append(mtg)
    return sorted(upcoming, key=lambda m: m["start"])


def build_meeting_context(meeting: dict, people: dict, emails: dict) -> str:
    start = datetime.fromisoformat(meeting["start"])
    end = datetime.fromisoformat(meeting["end"])
    duration_min = int((end - start).total_seconds() / 60)

    attendee_profiles = []
    for pid in meeting.get("people_involved", []):
        if pid == MY_PERSON_ID:
            continue
        person = people.get(pid)
        if person:
            attendee_profiles.append(
                f"- {person['name']} ({person['title']}, {person.get('department', '')})\n"
                f"  Relationship: {person.get('relationship', 'colleague')}\n"
                f"  Background: {person.get('bio', 'No bio available.')}\n"
                f"  Notes: {person.get('notes', '')}"
            )
        else:
            attendee_profiles.append(f"- Unknown person (id: {pid})")

    attendees_text = "\n".join(attendee_profiles) if attendee_profiles else "No attendee profiles found."

    related_email_ids = meeting.get("related_emails", [])
    email_snippets = []
    for eid in related_email_ids:
        email = emails.get(eid)
        if email:
            sender = people.get(email["from"], {}).get("name", email["from"])
            email_snippets.append(
                f"  [{email['sent_at']}] From {sender}: \"{email['subject']}\"\n"
                f"  {email['body']}"
            )
    emails_text = "\n\n".join(email_snippets) if email_snippets else "No related emails."

    history_text = (
        f"Notes from last meeting:\n{meeting['notes_from_last']}"
        if meeting.get("notes_from_last")
        else "No prior meeting history."
    )

    return f"""
MEETING: {meeting['title']}
Time: {start.strftime('%A %B %d, %Y at %I:%M %p')} ({duration_min} minutes)
Location: {meeting.get('location', 'TBD')}
Organizer: {people.get(meeting.get('organizer', ''), {}).get('name', meeting.get('organizer', 'Unknown'))}
Recurrence: {meeting.get('recurrence', 'unknown')}

AGENDA:
{meeting.get('agenda', 'No agenda provided.')}

ATTENDEES:
{attendees_text}

RELATED EMAILS:
{emails_text}

{history_text}
""".strip()


def generate_briefing(meeting_context: str, client: anthropic.Anthropic) -> str:
    prompt = f"""You are a personal executive assistant. Based on the meeting details below, generate a concise pre-meeting briefing.

Return ONLY a JSON object with these exact keys:
{{
  "summary": "one sentence on the purpose and what's at stake",
  "who_is_in_the_room": [
    {{"name": "Person Name", "role": "their title", "approach": "how to approach them"}}
  ],
  "what_to_know": ["bullet 1", "bullet 2", "bullet 3"],
  "talking_points": ["point 1", "point 2", "point 3", "point 4"],
  "watch_out_for": ["risk 1", "risk 2"]
}}

No markdown, no extra text, just the JSON object.

---
{meeting_context}
"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )
    text = message.content[0].text.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text)


def get_briefings(now: datetime = None) -> list:
    if now is None:
        now = datetime.now()

    meetings = load_all(MEETINGS_DIR)
    people = load_all(PEOPLE_DIR)
    emails = load_all(EMAILS_DIR)

    upcoming = get_upcoming_meetings(meetings, now, MINUTES_AHEAD)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set.")
    client = anthropic.Anthropic(api_key=api_key)

    results = []
    for meeting in upcoming:
        start = datetime.fromisoformat(meeting["start"])
        end = datetime.fromisoformat(meeting["end"])
        minutes_until = int((start - now).total_seconds() / 60)

        attendees = []
        for pid in meeting.get("people_involved", []):
            if pid == MY_PERSON_ID:
                continue
            person = people.get(pid)
            if person:
                attendees.append({
                    "name": person["name"],
                    "title": person["title"],
                    "department": person.get("department", ""),
                    "email": person.get("email", ""),
                    "notes": person.get("notes", ""),
                })

        context = build_meeting_context(meeting, people, emails)
        briefing = generate_briefing(context, client)

        results.append({
            "id": meeting["id"],
            "title": meeting["title"],
            "start": start.strftime("%I:%M %p"),
            "date": start.strftime("%A, %B %d"),
            "duration": int((end - start).total_seconds() / 60),
            "location": meeting.get("location", "TBD"),
            "recurrence": meeting.get("recurrence", ""),
            "minutes_until": minutes_until,
            "attendees": attendees,
            "agenda": meeting.get("agenda", ""),
            "briefing": briefing,
        })

    return results


if __name__ == "__main__":
    simulated_now = datetime(2026, 6, 26, 9, 0, 0)
    briefings = get_briefings(now=simulated_now)
    for b in briefings:
        print(f"\n{'='*60}")
        print(f"BRIEFING: {b['title']} at {b['start']}")
        print(json.dumps(b["briefing"], indent=2, ensure_ascii=False))
