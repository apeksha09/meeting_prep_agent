"""
Meeting Prep Agent
Reads mock calendar + people data, generates a briefing for upcoming meetings.
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
import anthropic

DATA_DIR = Path(__file__).parent / "data"
MINUTES_AHEAD = 120  # prep meetings starting within this window


def load_data():
    with open(DATA_DIR / "calendar.json") as f:
        calendar = json.load(f)
    with open(DATA_DIR / "people.json") as f:
        people = json.load(f)
    people_by_email = {p["email"]: p for p in people["people"]}
    return calendar["meetings"], people_by_email


def get_upcoming_meetings(meetings: list, now: datetime, window_minutes: int) -> list:
    upcoming = []
    cutoff = now + timedelta(minutes=window_minutes)
    for mtg in meetings:
        start = datetime.fromisoformat(mtg["start"])
        if now <= start <= cutoff:
            upcoming.append(mtg)
    return sorted(upcoming, key=lambda m: m["start"])


def build_meeting_context(meeting: dict, people_by_email: dict) -> str:
    start = datetime.fromisoformat(meeting["start"])
    end = datetime.fromisoformat(meeting["end"])
    duration_min = int((end - start).total_seconds() / 60)

    attendee_profiles = []
    for email in meeting["attendees"]:
        if email == "you@company.com":
            continue
        person = people_by_email.get(email)
        if person:
            attendee_profiles.append(
                f"- {person['name']} ({person['title']}, {person['department']})\n"
                f"  Relationship: {person['relationship']}\n"
                f"  Background: {person['bio']}\n"
                f"  Notes: {person['notes']}"
            )
        else:
            attendee_profiles.append(f"- {email} (no profile available)")

    attendees_text = "\n".join(attendee_profiles) if attendee_profiles else "No attendee profiles found."

    last_notes = meeting.get("notes_from_last")
    history_text = f"Notes from last meeting:\n{last_notes}" if last_notes else "No prior meeting history."

    docs_text = ", ".join(meeting["linked_docs"]) if meeting["linked_docs"] else "None"

    return f"""
MEETING: {meeting['title']}
Time: {start.strftime('%A %B %d, %Y at %I:%M %p')} ({duration_min} minutes)
Location: {meeting.get('location', 'TBD')}
Organizer: {meeting['organizer']}
Recurrence: {meeting.get('recurrence', 'unknown')}

AGENDA:
{meeting.get('agenda', 'No agenda provided.')}

ATTENDEES:
{attendees_text}

LINKED DOCUMENTS: {docs_text}

{history_text}
""".strip()


def generate_briefing(meeting_context: str, client: anthropic.Anthropic) -> str:
    prompt = f"""You are a personal executive assistant. Based on the meeting details below, generate a concise pre-meeting briefing.

The briefing should include:
1. **Meeting Summary** — one sentence on the purpose and what's at stake
2. **Who's in the Room** — key facts about each attendee and how to approach them
3. **What to Know** — relevant context, history, open items from last time
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

    print(f"Meeting Prep Agent running — checking meetings for the next {MINUTES_AHEAD} minutes...")
    print(f"Current time: {now.strftime('%A %B %d, %Y at %I:%M %p')}\n")

    meetings, people_by_email = load_data()
    upcoming = get_upcoming_meetings(meetings, now, MINUTES_AHEAD)

    if not upcoming:
        print("No upcoming meetings in the next window. Enjoy the focus time.")
        return

    print(f"Found {len(upcoming)} upcoming meeting(s).\n{'='*60}\n")

    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    for meeting in upcoming:
        start = datetime.fromisoformat(meeting["start"])
        minutes_until = int((start - now).total_seconds() / 60)

        print(f"BRIEFING: {meeting['title']}")
        print(f"Starts in {minutes_until} minutes\n")

        context = build_meeting_context(meeting, people_by_email)
        briefing = generate_briefing(context, client)

        print(briefing)
        print(f"\n{'='*60}\n")


if __name__ == "__main__":
    # Simulate "now" as just before the Q3 Strategy Review and 1:1
    simulated_now = datetime(2026, 6, 25, 9, 15, 0)
    run(now=simulated_now)
