# agents/specialists/zodiac.py
import os
import sys

# Add project root to sys.path so python can find 'utils' when this script is run directly
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from datetime import date
from typing import Optional

from google.genai import types

from utils.config import client, MODEL
from utils.persona import SHARED_RULES

SPECIALIST_NAME = "zodiac"


# --- The tool: deterministic sun-sign lookup ------------------------------

# Each entry is the LAST day of that sign's window. A date belongs to the
# first sign whose end-date is >= the date. Capricorn appears twice because
# it wraps the year end (Dec 22 – Jan 19).
_ZODIAC_CUTOFFS = [
    ("Capricorn", (1, 19)), ("Aquarius", (2, 18)), ("Pisces", (3, 20)),
    ("Aries", (4, 19)), ("Taurus", (5, 20)), ("Gemini", (6, 20)),
    ("Cancer", (7, 22)), ("Leo", (8, 22)), ("Virgo", (9, 22)),
    ("Libra", (10, 22)), ("Scorpio", (11, 21)), ("Sagittarius", (12, 21)),
    ("Capricorn", (12, 31)),
]


def get_sun_sign(month: int, day: int) -> str:
    """Return the Western tropical sun sign for a birth date. Pure lookup —
    no model guessing. This is the honest 'math by function' piece."""
    for sign, (m, d) in _ZODIAC_CUTOFFS:
        if (month, day) <= (m, d):
            return sign
    return "Capricorn"  # unreachable, but keeps the type checker happy


def _parse_birth_date(raw) -> Optional[date]:
    """Accept a date object or an ISO 'YYYY-MM-DD' string; None if unparseable."""
    if isinstance(raw, date):
        return raw
    try:
        return date.fromisoformat(str(raw).strip())
    except (ValueError, TypeError):
        return None


# --- The astrologer's voice (zodiac-specific; shared rules appended) ------

ZODIAC_PERSONA = """
You are an expert Western Astrologer at Cosmic Concierge. You are highly
proficient in interpreting natal (birth) charts, synastry, planetary transits,
and celestial phenomena.

# What you are given
You will be given the user's question, their birth details, and their SUN SIGN
— which has already been calculated for you. Use the sun sign you are given as
the anchor of the reading; do not recompute or second-guess it.

- With only the birth DATE, read primarily from the sun sign, and mention that
  an exact birth time and city would let you speak to their rising sign and
  house placements for a fuller chart.
- With birth TIME and PLACE also given, you may speak more fully and
  interpretively about the natal chart — rising sign, moon, house emphasis.
  Do NOT invent precise degrees or placements you cannot know; keep it
  qualitative and grounded in the sun sign you were given.

# How to read
Connect the astrological picture to THIS person's specific question. Weave it
into one coherent narrative rather than listing traits in isolation. Speak
directly to the person, and keep it to 3-4 short paragraphs.
"""

ZODIAC_PROMPT = ZODIAC_PERSONA + SHARED_RULES


# --- The specialist interface (matches the stub) --------------------------

def run(user_message: str, context: dict) -> str:
    """Read the user's chart. Called by the orchestrator.

    Expects birth details in context (populated by a Streamlit form or by an
    earlier turn via memory):
        context["birth_date"]  -> "YYYY-MM-DD" or a date object   (required)
        context["birth_time"]  -> e.g. "14:30"                    (optional)
        context["birth_place"] -> e.g. "Taipei, Taiwan"           (optional)
    """
    # Directive 1: gather necessary data before reading.
    birth_date = _parse_birth_date(context.get("birth_date"))
    if birth_date is None:
        return ("To read your chart, I'll need your birth details. Could you "
                "share your **date of birth**, and — if you know them — your "
                "**exact time of birth** and **city**? The time and place let "
                "me go beyond your sun sign into a fuller natal picture.")

    sun_sign = get_sun_sign(birth_date.month, birth_date.day)
    birth_time = context.get("birth_time")
    birth_place = context.get("birth_place")

    details = [f"Birth date: {birth_date.isoformat()}", f"Sun sign: {sun_sign}"]
    if birth_time:
        details.append(f"Birth time: {birth_time}")
    if birth_place:
        details.append(f"Birth place: {birth_place}")
    details_block = "\n".join(f"  {d}" for d in details)

    history = context.get("history", "")
    history_block = f"\nEarlier in the conversation:\n{history}\n" if history else ""

    contents = (
        f'The user asked: "{user_message}"\n'
        f"{history_block}"
        f"\nTheir birth details:\n{details_block}\n\n"
        f"Give the reading, anchored on the sun sign above."
    )

    response = client.models.generate_content(
        model=MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=ZODIAC_PROMPT,
            temperature=0.9,
        ),
    )
    return response.text


# --- Quick standalone test (run from repo root) ---------------------------
#     python -m agents.specialists.zodiac
if __name__ == "__main__":
    # No birth data -> should ask for it
    print(run("Why do I struggle with commitment?", {}))
    print("\n" + "=" * 60 + "\n")
    # With birth data -> should give a reading
    ctx = {"birth_date": "1994-04-25", "birth_time": "14:30",
           "birth_place": "Taipei, Taiwan"}
    print(run("Why do I struggle with commitment?", ctx))