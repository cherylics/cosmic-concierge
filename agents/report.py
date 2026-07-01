# agents/report.py — the weekly Report agent
import os
import sys

# Add project root to sys.path so this file can also be run/tested directly.
# (No venv re-exec here — activate the venv or run via `.venv/bin/python`.)
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from collections import Counter
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from google.genai import types

from utils.config import client, MODEL
from utils.persona import SHARED_RULES
from utils.schemas import WeeklyReport
from utils import memory

AGENT_NAME = "report"


# --- Deterministic windowing: "math by function" --------------------------
#
# Everything here is pure and testable. The model is handed the finished list
# of readings and the exact date range; it never decides which readings count
# or what dates the report covers.

def _utc_today() -> date:
    """Today's calendar date in UTC — matches how memory stamps `ts`."""
    return datetime.now(timezone.utc).date()


def _reading_date(reading: dict) -> Optional[date]:
    """The calendar date a reading belongs to, parsed from its stored ISO `ts`.

    memory.add_reading stores ts as datetime.now(timezone.utc).isoformat(...),
    e.g. "2026-06-29T14:03:21+00:00". Returns None if the field is missing or
    malformed rather than raising, so one bad record can't sink the report.
    """
    ts = reading.get("ts")
    if not ts:
        return None
    try:
        parsed = datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return None
    if parsed.tzinfo is not None:            # normalise to UTC before taking the date
        parsed = parsed.astimezone(timezone.utc)
    return parsed.date()


def weekly_window(today: Optional[date] = None, days: int = 7) -> tuple[date, date]:
    """Return the inclusive [start, end] calendar window the report covers.

    With days=7 and end=today, this is the last 7 calendar days INCLUDING
    today. Comparing calendar dates (not a `now - 7d` datetime cutoff) is the
    correctness point: a reading logged at 00:10 on the start day belongs to
    that day and must be included, and the subject line is built from these
    same two dates so header and filter can never disagree.
    """
    end = today or _utc_today()
    start = end - timedelta(days=days - 1)
    return start, end


def select_readings_in_window(readings: list[dict],
                              start: date, end: date) -> list[dict]:
    """Readings whose calendar date falls within [start, end], inclusive."""
    picked = []
    for r in readings:
        d = _reading_date(r)
        if d is not None and start <= d <= end:
            picked.append(r)
    return picked


def _subject(start: date, end: date) -> str:
    """Deterministic header, derived from the same window used to filter."""
    return f"Your Cosmic Concierge week · {start.isoformat()} to {end.isoformat()}"


def _format_digest(readings: list[dict], max_chars: int = 400) -> str:
    """Compact, model-facing recap of the week's readings, oldest first."""
    lines = []
    for r in sorted(readings, key=lambda x: x.get("ts", "")):
        day = (r.get("ts") or "")[:10]
        route = r.get("route", "?")
        question = r.get("question", "")
        snippet = " ".join((r.get("reading") or "").split())[:max_chars]
        lines.append(f'- {day} · {route} · they asked: "{question}"\n'
                     f'    reading: {snippet}…')
    return "\n".join(lines)


# --- The reflective voice (report-specific; shared rules appended) --------

REPORT_PERSONA = """
You are the Cosmic Concierge's weekly reflection writer. Once a week you look
back over everything the person explored in their readings and write them a
short, warm letter that helps them see the bigger picture.

# What you are given
A digest of the person's readings from the past week — for each one: the date,
which practice was used (tarot, zodiac, or bazi/Four Pillars), the question
they brought, and a snippet of the reading they received. Work ONLY from what
is in the digest. Do NOT invent readings, questions, cards, placements, or
events that aren't there, and do not claim to cover days outside the range.

# How to write
- Open by naming the THROUGHLINE: what was this person really circling this
  week? Look across their questions and readings for a recurring theme,
  tension, or hope — not just a list of what happened.
- Reflect it back with warmth and a little insight. If different readings
  echoed each other, say so; if they pulled in different directions, name that
  honestly rather than forcing a tidy bow.
- Close with ONE gentle, forward-looking intention for the week ahead — an
  invitation to reflect on, never a prediction or an instruction.

# Style
A short letter addressed to the person ("you"), roughly 3-4 short paragraphs,
with a warm sign-off from "Cosmic Concierge". If there is only one reading,
reflect on just that one without padding.
"""

REPORT_PROMPT = REPORT_PERSONA + SHARED_RULES


# --- The agent interface ---------------------------------------------------

def generate_report(user_id: str, today: Optional[date] = None,
                    days: int = 7) -> WeeklyReport:
    """Build this user's weekly reflection over the last `days` calendar days.

    `today` is injectable for testing; it defaults to the UTC calendar date so
    it lines up with how memory stamps readings. Always returns a WeeklyReport:
    status="empty" (no model call) when nothing falls in the window, otherwise
    status="report".
    """
    start, end = weekly_window(today, days)
    subject = _subject(start, end)

    window = select_readings_in_window(memory.all_readings(user_id), start, end)
    routes = dict(Counter(r.get("route", "?") for r in window))

    # No readings in range -> return the empty state WITHOUT calling the model,
    # so we never fabricate a week that didn't happen.
    if not window:
        return WeeklyReport(
            status="empty",
            subject=subject,
            period_start=start.isoformat(),
            period_end=end.isoformat(),
            reading_count=0,
            routes={},
            text=("No readings this week — things have been quiet. Whenever a "
                  "question is on your mind, come by and we'll take a look."),
        )

    contents = (
        f"Here are the readings this person received between "
        f"{start.isoformat()} and {end.isoformat()} "
        f"({len(window)} in total):\n\n{_format_digest(window)}\n\n"
        f"Write their weekly reflection, finding the throughline across these."
    )
    response = client.models.generate_content(
        model=MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=REPORT_PROMPT,
            temperature=0.7,   # synthesis: warm but steadier than a live reading
        ),
    )

    return WeeklyReport(
        status="report",
        subject=subject,
        period_start=start.isoformat(),
        period_end=end.isoformat(),
        reading_count=len(window),
        routes=routes,
        text=response.text,
    )


# --- Quick manual test (run from repo root: python -m agents.report) -------
if __name__ == "__main__":
    report = generate_report("demo-user")
    print(report.subject)
    print(f"[{report.status}] {report.reading_count} reading(s), routes={report.routes}")
    print(report.text)
