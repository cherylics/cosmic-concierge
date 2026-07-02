# utils/chat.py — the seam between the Streamlit UI and the agent layer.
#
# app.py stays thin: for each user turn it calls handle_turn(...) and drops the
# returned HTML into a chat bubble. All the agent wiring — routing, birth-detail
# capture, memory logging, markdown rendering — lives here where it can be
# tested without spinning up Streamlit.
import os
import sys
import re
import html as _html
from datetime import date
from typing import Optional

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from agents.orchestrator import concierge
from utils import memory

# Cards that map to a specific specialist. The "cosmic" card (and anything else)
# falls through to the router.
_DIRECT_PRACTICES = {"tarot", "zodiac", "bazi"}


# --- Markdown -> HTML ------------------------------------------------------
# Readings come back as markdown (bold, bullets) but the chat bubbles inject raw
# HTML, so we convert. Uses the `markdown` package when available; otherwise a
# small fallback that at least handles bold/italic and line breaks.
try:
    import markdown as _markdown

    def md_to_html(text: str) -> str:
        return _markdown.markdown(text or "", extensions=["nl2br", "sane_lists"])
except Exception:  # markdown not installed — degrade gracefully
    def md_to_html(text: str) -> str:
        esc = _html.escape(text or "")
        esc = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", esc)
        esc = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", esc)
        return esc.replace("\n", "<br>")


# --- Opportunistic birth-detail capture ------------------------------------
# The UI is free-text, but zodiac/bazi need structured birth data. When the user
# types their details in reply to a "need_input" prompt, pull them out and
# persist to the memory profile so the next turn can complete the reading.
#
# This is a pragmatic bridge, not a parser for every phrasing. A dedicated
# birth-details form would be more robust; see the note in the review.
# ISO-ish: 1995-01-05, 1995/1/5
_DATE_RE = re.compile(r"\b(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})\b")
# US numeric: 1/5/1995 (interpreted month-first)
_DATE_US_RE = re.compile(r"\b(\d{1,2})[/](\d{1,2})[/](\d{4})\b")
# Month-name: "Jan 5th 1995", "January 5, 1995", "5 Jan 1995"
_MONTHS = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun",
     "jul", "aug", "sep", "oct", "nov", "dec"])}
_DATE_NAME_RE = re.compile(
    r"\b(?:(\d{1,2})(?:st|nd|rd|th)?\s+)?"          # optional leading day
    r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?"
    r"(?:\s+(\d{1,2})(?:st|nd|rd|th)?)?,?\s+(\d{4})\b",
    re.IGNORECASE)
# 24h "14:30" or 12h "2:30 pm"; "6pm" also accepted
_TIME_RE = re.compile(
    r"\b(\d{1,2})(?::([0-5]\d))?\s*(am|pm|a\.m\.|p\.m\.)?\b", re.IGNORECASE)


def _extract_date(message: str):
    """Return a date found in free text, or None. Tries ISO, US, month-name."""
    m = _DATE_RE.search(message)
    if m:
        y, mo, d = (int(g) for g in m.groups())
        return _safe_date(y, mo, d)
    m = _DATE_US_RE.search(message)
    if m:
        mo, d, y = (int(g) for g in m.groups())
        return _safe_date(y, mo, d)
    m = _DATE_NAME_RE.search(message)
    if m:
        day_a, mon, day_b, year = m.groups()
        day = day_a or day_b
        if day:
            return _safe_date(int(year), _MONTHS[mon.lower()[:3]], int(day))
    return None


def _safe_date(y: int, mo: int, d: int):
    try:
        return date(y, mo, d)
    except ValueError:      # e.g. 2024-13-40 — ignore rather than store a bad date
        return None


def _extract_time(message: str):
    """Return 'HH:MM' (24h) from '14:30', '2:30 pm', or '6pm'; else None.

    A bare number with no colon and no am/pm is NOT treated as a time —
    otherwise the day in 'Jan 5th 1995' would be captured as 05:00.
    """
    for m in _TIME_RE.finditer(message):
        h, mins, ampm = m.group(1), m.group(2) or "00", m.group(3)
        if mins == "00" and m.group(2) is None and not ampm:
            continue                       # bare number, not a time
        h = int(h)
        if ampm:
            ampm = ampm.lower().replace(".", "")
            if not 1 <= h <= 12:
                continue
            if ampm == "pm" and h != 12:
                h += 12
            elif ampm == "am" and h == 12:
                h = 0
        elif not 0 <= h <= 23:
            continue
        return f"{h:02d}:{mins}"
    return None
_FEMALE_RE = re.compile(r"\b(female|woman|girl)\b", re.IGNORECASE)
_MALE_RE = re.compile(r"\b(male|man|boy)\b", re.IGNORECASE)


def capture_birth_details(user_id: str, message: str) -> dict:
    """Extract any birth date / time / gender from a message and persist them.

    Returns the fields found (may be empty). Safe to call on every turn.
    """
    fields: dict = {}

    d = _extract_date(message)
    if d:
        fields["birth_date"] = d.isoformat()

    t = _extract_time(message)
    if t:
        fields["birth_time"] = t

    # Check female before male so "female" doesn't trip the "male" pattern.
    if _FEMALE_RE.search(message):
        fields["gender"] = "female"
    elif _MALE_RE.search(message):
        fields["gender"] = "male"

    if fields:
        memory.update_profile(user_id, **fields)
    return fields


# --- Rendering a result to HTML --------------------------------------------

def _result_to_html(result) -> str:
    """Turn a ConciergeResult into the HTML shown in the assistant bubble."""
    parts = []
    if result.status == "reading":
        if result.concierge_message:                    # router handoff line, if any
            parts.append(md_to_html(result.concierge_message))
        parts.append(md_to_html(result.reading or ""))
    else:
        # need_input / clarify / out_of_scope — the message IS the content
        parts.append(md_to_html(result.concierge_message))
    return "<br><br>".join(p for p in parts if p)


# --- The one call app.py makes ---------------------------------------------

def handle_turn(user_id: str, active_agent: Optional[str], user_message: str) -> tuple[str, str, str]:
    """Run one user turn through the agent layer and return (HTML, route, status).

    - captures any birth details from the message into the profile
    - builds context (profile + recent-reading recap) from memory
    - routes: a specific practice card goes straight to that specialist; the
      "cosmic" card (or None) goes through the router
    - logs ONLY completed readings to memory
    """
    capture_birth_details(user_id, user_message)

    context = memory.build_context(user_id)
    forced = active_agent if active_agent in _DIRECT_PRACTICES else None

    result = concierge(user_message, context, forced_route=forced)

    if result.is_reading:
        memory.add_reading(user_id, result.route, user_message, result.reading)

    return _result_to_html(result), result.route, result.status