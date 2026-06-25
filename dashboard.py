import os
from datetime import datetime

import anthropic
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template

from agent import (
    EMAILS_DIR,
    MEETINGS_DIR,
    MINUTES_AHEAD,
    PEOPLE_DIR,
    build_meeting_context,
    generate_briefing,
    get_upcoming_meetings,
    load_all,
)

load_dotenv()

app = Flask(__name__)

# Stores generated briefings for the active dashboard process.
BRIEFINGS_BY_MEETING_ID = {}


def build_anthropic_client() -> anthropic.Anthropic:
    auth_token = os.environ.get("ANTHROPIC_AUTH_TOKEN")
    api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("API_KEY")

    if auth_token:
        return anthropic.Anthropic(auth_token=auth_token)
    if api_key:
        return anthropic.Anthropic(api_key=api_key)

    raise RuntimeError(
        "Missing Anthropic credentials. Set ANTHROPIC_AUTH_TOKEN, "
        "ANTHROPIC_API_KEY, or API_KEY."
    )


def load_dashboard_data() -> tuple[dict, dict, dict]:
    meetings = load_all(MEETINGS_DIR)
    people = load_all(PEOPLE_DIR)
    emails = load_all(EMAILS_DIR)
    return meetings, people, emails


@app.get("/")
def index():
    return render_template("dashboard.html")


@app.get("/api/meetings")
def list_meetings():
    meetings, _, _ = load_dashboard_data()
    events = []
    for meeting in meetings.values():
        if "start" not in meeting:
            continue
        meeting_id = meeting["id"]
        events.append(
            {
                "id": meeting_id,
                "title": meeting.get("title", meeting_id),
                "start": meeting["start"],
                "end": meeting.get("end"),
                "location": meeting.get("location", "TBD"),
                "has_briefing": meeting_id in BRIEFINGS_BY_MEETING_ID,
            }
        )

    events.sort(key=lambda event: event["start"])
    return jsonify({"events": events})


@app.post("/api/run-agent")
def run_agent():
    meetings, people, emails = load_dashboard_data()
    now = datetime.now()
    upcoming = get_upcoming_meetings(meetings, now, MINUTES_AHEAD)

    if not upcoming:
        return jsonify(
            {
                "message": "No upcoming meetings in the configured window.",
                "generated": [],
            }
        )

    client = build_anthropic_client()
    generated = []

    for meeting in upcoming:
        context = build_meeting_context(meeting, people, emails)
        briefing = generate_briefing(context, client)

        BRIEFINGS_BY_MEETING_ID[meeting["id"]] = {
            "meeting_id": meeting["id"],
            "title": meeting.get("title", meeting["id"]),
            "briefing": briefing,
            "generated_at": now.isoformat(timespec="seconds"),
        }
        generated.append(
            {
                "meeting_id": meeting["id"],
                "title": meeting.get("title", meeting["id"]),
            }
        )

    return jsonify(
        {
            "message": f"Generated {len(generated)} briefing(s).",
            "generated": generated,
        }
    )


@app.get("/api/briefings")
def list_briefings():
    items = sorted(
        BRIEFINGS_BY_MEETING_ID.values(),
        key=lambda item: item["generated_at"],
        reverse=True,
    )
    return jsonify({"briefings": items})


@app.get("/api/briefings/<meeting_id>")
def get_briefing(meeting_id: str):
    briefing = BRIEFINGS_BY_MEETING_ID.get(meeting_id)
    if not briefing:
        return jsonify({"error": "No briefing found for this meeting yet."}), 404
    return jsonify(briefing)


if __name__ == "__main__":
    app.run(debug=True)