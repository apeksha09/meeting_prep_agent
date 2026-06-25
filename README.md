# Meeting Prep Agent

An AI agent that reads your calendar data and generates a concise pre-meeting briefing — attendee profiles, agenda context, relevant emails, talking points, and risks — powered by Claude.

## How it works

1. Reads upcoming meetings from `meetings/` within a configurable time window
2. Looks up attendee profiles from `people/`
3. Pulls related emails from `emails/`
4. Sends all context to Claude, which generates a structured briefing
5. Prints the briefing to the terminal (extend to email/Slack as needed)

## Setup

```bash
# 1. Clone the repo
git clone https://github.com/apeksha09/meeting_prep_agent.git
cd meeting_prep_agent

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set your Anthropic API key
cp .env.example .env
# Edit .env and add your key, then:
export ANTHROPIC_API_KEY=your-key-here   # Mac/Linux
set ANTHROPIC_API_KEY=your-key-here      # Windows

# 4. Run the agent
python agent.py

# 5. Run the dashboard
python dashboard.py
# Open http://127.0.0.1:5000
```

## Configuration

In `agent.py`:
- `MY_PERSON_ID` — set to your person ID in `people/` (default: `"p1"` = Ava Patel)
- `MINUTES_AHEAD` — how far ahead to look for meetings (default: 120 minutes)
- `simulated_now` — change this to test different times

## Dashboard

- **Calendar tab**: displays all meetings on a calendar
- **Run Agent button**: generates briefings for upcoming meetings
- **Clickable meetings**: meetings with generated briefings become clickable and open the briefing view

## Data structure

```
meetings/     # One JSON per meeting — title, start/end, attendees, agenda, notes
people/       # One JSON per person — name, title, bio, relationship, notes
emails/       # One JSON per email — from, to, subject, body, linked to meetings
```

## Extending

- **Scheduler**: run `agent.py` every 30 min via cron or Windows Task Scheduler
- **Delivery**: pipe output to an email or Slack bot instead of printing
- **Real data**: swap mock JSON files for Google Calendar / Outlook API calls
