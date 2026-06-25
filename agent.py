"""
Meeting Prep Agent
Reads meetings/, people/, and emails/ data, generates a pre-meeting briefing via Claude.
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
import anthropic
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
MEETINGS_DIR = BASE_DIR / "meetings"
PEOPLE_DIR = BASE_DIR / "people"
EMAILS_DIR = BASE_DIR / "emails"

MY_PERSON_ID = "p1"       # change to match your person ID in people/
MINUTES_AHEAD = 12000        # prep meetings starting within this window


def load_all(directory: Path) -> dict:
    """Load all JSON files from a directory, keyed by id."""
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

    # Attendee profiles (skip yourself)
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

    # Related emails
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

The briefing should include:
1. **Meeting Summary** — one sentence on the purpose and what's at stake
2. **Who's in the Room** — key facts about each attendee and how to approach them
3. **What to Know** — relevant context, history, and key points from related emails
4. **Suggested Talking Points** — 3–5 concrete things to raise or be ready to discuss
5. **Watch Out For** — any risks, sensitivities, or dynamics to be aware of

Keep it tight and actionable. No fluff.

---
{meeting_context}
"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )
    return message.content[0].text


def run(now: datetime = None):
    if now is None:
        now = datetime.now()

    print(f"Meeting Prep Agent — checking next {MINUTES_AHEAD} minutes of meetings")
    print(f"Current time: {now.strftime('%A %B %d, %Y at %I:%M %p')}\n")

    meetings = load_all(MEETINGS_DIR)
    people = load_all(PEOPLE_DIR)
    emails = load_all(EMAILS_DIR)

    upcoming = get_upcoming_meetings(meetings, now, MINUTES_AHEAD)

    if not upcoming:
        print("No upcoming meetings in the window. Enjoy the focus time.")
        return

    print(f"Found {len(upcoming)} upcoming meeting(s).\n{'='*60}\n")

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set.")
    client = anthropic.Anthropic(api_key=api_key)

    for meeting in upcoming:
        start = datetime.fromisoformat(meeting["start"])
        minutes_until = int((start - now).total_seconds() / 60)

        print(f"BRIEFING: {meeting['title']}")
        print(f"Starts in {minutes_until} minutes\n")

        context = build_meeting_context(meeting, people, emails)
        briefing = generate_briefing(context, client)

        print(briefing)
        print(f"\n{'='*60}\n")


if __name__ == "__main__":
    # Simulates running at 9:30 AM on June 25 — picks up meetings starting before 11:30 AM
    simulated_now = datetime(2026, 6, 26, 9, 0, 0)
    run(now=simulated_now)
