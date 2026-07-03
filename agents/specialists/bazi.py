# agents/specialists/bazi.py
import os
import sys

# Add project root to sys.path so python can find 'utils' when this script is run directly
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from datetime import date
from typing import Optional

from google.genai import types
from lunar_python import Solar

from utils.config import client, MODEL
from utils.persona import SHARED_RULES
from utils.schemas import SpecialistReply

SPECIALIST_NAME = "bazi"


# --- The tool: deterministic Four Pillars + Five Elements calculator -------
#
# The pillars, day master, element balance, and luck cycles are all computed
# by lunar_python from the birth moment. The model NEVER computes these — it
# only interprets the numbers it is handed. This is the honest "math by
# function, meaning by model" pattern, same as tarot's card draw.

_STEM_ELEMENT = {"甲": "Wood", "乙": "Wood", "丙": "Fire", "丁": "Fire",
                 "戊": "Earth", "己": "Earth", "庚": "Metal", "辛": "Metal",
                 "壬": "Water", "癸": "Water"}
_BRANCH_ELEMENT = {"子": "Water", "丑": "Earth", "寅": "Wood", "卯": "Wood",
                   "辰": "Earth", "巳": "Fire", "午": "Fire", "未": "Earth",
                   "申": "Metal", "酉": "Metal", "戌": "Earth", "亥": "Water"}
# Heavenly stems alternate yang, yin, yang, yin...
_STEM_POLARITY = {"甲": "yang", "乙": "yin", "丙": "yang", "丁": "yin",
                  "戊": "yang", "己": "yin", "庚": "yang", "辛": "yin",
                  "壬": "yang", "癸": "yin"}


def calculate_bazi(year: int, month: int, day: int,
                   hour: int, minute: int = 0,
                   gender: Optional[int] = None,
                   hour_known: bool = True) -> dict:
    """Compute the Four Pillars chart from a birth moment.

    gender: 1 = male, 0 = female (needed only for the luck-cycle direction).
            If None, luck cycles are omitted.
    hour_known: when False (user doesn't know their birth time), the hour
            pillar is EXCLUDED from the chart and element counts — a classic
            three-pillar reading — rather than fabricating an hour.
    Returns a plain dict the reader agent can interpret.
    """
    solar = Solar.fromYmdHms(year, month, day, hour, minute, 0)
    ec = solar.getLunar().getEightChar()

    stems = [ec.getYearGan(), ec.getMonthGan(), ec.getDayGan()]
    branches = [ec.getYearZhi(), ec.getMonthZhi(), ec.getDayZhi()]
    if hour_known:
        stems.append(ec.getTimeGan())
        branches.append(ec.getTimeZhi())

    # Count the five elements across all 8 characters (main elements only;
    # hidden stems inside branches are a professional refinement we don't add).
    counts = {e: 0 for e in ("Wood", "Fire", "Earth", "Metal", "Water")}
    for s in stems:
        counts[_STEM_ELEMENT[s]] += 1
    for b in branches:
        counts[_BRANCH_ELEMENT[b]] += 1

    day_stem = ec.getDayGan()
    peak = max(counts.values())

    result = {
        "pillars": {
            "year": ec.getYear(), "month": ec.getMonth(),
            "day": ec.getDay(),
            "hour": ec.getTime() if hour_known else "unknown (three-pillar reading)",
        },
        "day_master": {
            "stem": day_stem,
            "element": _STEM_ELEMENT[day_stem],
            "polarity": _STEM_POLARITY[day_stem],
        },
        "element_counts": counts,
        "missing_elements": [e for e, c in counts.items() if c == 0],
        "dominant_elements": [e for e, c in counts.items() if c == peak],
        "luck_cycles": None,
    }

    # Da Yun — the decade luck cycles that carry the long-term trajectory.
    if gender is not None:
        yun = ec.getYun(gender)
        cycles = []
        for d in yun.getDaYun():
            gz = d.getGanZhi()
            if not gz:            # first (pre-luck) period has no ganzhi; skip it
                continue
            cycles.append({
                "start_age": d.getStartAge(),
                "start_year": d.getStartYear(),
                "ganzhi": gz,
                "stem_element": _STEM_ELEMENT[gz[0]],
                "branch_element": _BRANCH_ELEMENT[gz[1]],
            })
        result["luck_cycles"] = cycles[:6]   # first ~6 decades is plenty

    return result


# --- Input parsing helpers -------------------------------------------------

def _parse_birth_date(raw) -> Optional[date]:
    if isinstance(raw, date):
        return raw
    try:
        return date.fromisoformat(str(raw).strip())
    except (ValueError, TypeError):
        return None


def _parse_time(raw) -> Optional[tuple[int, int]]:
    """Accept 'HH:MM' (24h). Returns (hour, minute) or None."""
    try:
        parts = str(raw).strip().split(":")
        h, m = int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
        if 0 <= h <= 23 and 0 <= m <= 59:
            return h, m
    except (ValueError, TypeError, IndexError):
        pass
    return None


def _parse_gender(raw) -> Optional[int]:
    """Map various forms to 1 (male) / 0 (female); None if absent/unknown."""
    if raw is None:
        return None
    s = str(raw).strip().lower()
    if s in ("male", "m", "1", "man"):
        return 1
    if s in ("female", "f", "0", "woman"):
        return 0
    return None


# --- The reader's voice (bazi-specific; shared rules appended) -------------

BAZI_PERSONA = """
You are a traditional Chinese fortune teller at Cosmic Concierge, highly
proficient in Bazi (the Four Pillars of Destiny), the I Ching, Daoist
philosophy, and Zhouyi.

# What you are given
The person's Four Pillars chart has ALREADY been calculated for you: the four
pillars, the Day Master (day stem), the distribution of the Five Elements, any
missing or dominant elements, and their decade luck cycles (Da Yun). Use these
figures as given — do NOT recompute or invent pillars, elements, or dates.

# How to read
- Anchor the reading on the DAY MASTER — its element and yang/yin polarity is
  the person themselves. Describe their core nature from it.
- Read the ELEMENTAL BALANCE: a missing element often points to what the person
  should cultivate; a dominant element to a strength that can tip into excess.
  Explain what each element represents in plain terms (e.g. Water =
  adaptability and wisdom, Fire = passion and visibility) — the user is not
  expected to know the system.
- Use the LUCK CYCLES (Da Yun) for the long-term trajectory: name which life
  stages carry which elemental energy, and what each decade invites them to
  focus on. This long view is the heart of a Bazi reading.

- If the hour pillar is marked unknown, this is a THREE-PILLAR reading: note
  briefly and warmly that the hour would add finer detail, then read the three
  pillars with full confidence — do not dwell on what's missing.

# Style
Weave the pillars, elements, and cycles into one flowing narrative addressed to
the person — not a table of definitions. Keep it to roughly 4-6 short
paragraphs given the long-term scope.
"""

BAZI_PROMPT = BAZI_PERSONA + SHARED_RULES


# --- The specialist interface (matches the stub) --------------------------

def _format_chart(chart: dict) -> str:
    p = chart["pillars"]
    dm = chart["day_master"]
    lines = [
        f"Four Pillars — Year: {p['year']}, Month: {p['month']}, "
        f"Day: {p['day']}, Hour: {p['hour']}",
        f"Day Master: {dm['stem']} ({dm['polarity']} {dm['element']})",
        f"Five Elements count: {chart['element_counts']}",
        f"Missing: {chart['missing_elements'] or 'none'}",
        f"Dominant: {chart['dominant_elements']}",
    ]
    if chart["luck_cycles"]:
        cyc = "; ".join(
            f"age {c['start_age']} ({c['start_year']}): {c['ganzhi']} "
            f"[{c['stem_element']}/{c['branch_element']}]"
            for c in chart["luck_cycles"]
        )
        lines.append(f"Luck cycles (Da Yun): {cyc}")
    return "\n".join(f"  {ln}" for ln in lines)


def run(user_message: str, context: dict) -> SpecialistReply:
    """Compute the chart and return a long-term reading. Called by orchestrator.

    Expects in context (from a Streamlit form or an earlier turn via memory):
        context["birth_date"]  -> "YYYY-MM-DD" or date   (required)
        context["birth_time"]  -> "HH:MM" 24h            (required for the hour pillar)
        context["gender"]      -> "male"/"female"        (needed for luck cycles)
        context["birth_place"] -> city                   (optional, for context)
    """
    birth_date = _parse_birth_date(context.get("birth_date"))
    birth_time = _parse_time(context.get("birth_time"))
    # Escape hatch: the user told us they don't know their birth hour.
    # We proceed with a three-pillar reading instead of looping forever.
    time_unknown = str(context.get("birth_time", "")).strip().lower() == "unknown"

    # Directive 1: gather necessary data before reading. Bazi needs date + time
    # (or an explicit "unknown" for a three-pillar reading).
    if birth_date is None or (birth_time is None and not time_unknown):
        missing = []
        if birth_date is None:
            missing.append("birth_date")
        if birth_time is None:
            missing.append("birth_time")

        # Compose the ask from the FULL known state (date, time, gender) so a
        # partial answer never gets the same message back verbatim — that
        # reads to the user like a bug. Acknowledge everything we have, ask
        # only for what's missing, and never re-ask for gender once given.
        gender_known = _parse_gender(context.get("gender")) is not None
        have = []
        if birth_date is not None:
            nice = f"{birth_date.strftime('%B')} {birth_date.day}, {birth_date.year}"
            have.append(f"your birth date (**{nice}**)")
        if gender_known:
            have.append(f"your luck cycles set to **{context.get('gender')}**")

        ask = []
        if birth_date is None:
            ask.append("your **exact birth date**")
        if birth_time is None:
            ask.append("your **time of birth** (e.g. 14:30 or 2:30 pm) — the "
                       "hour sets one of the four pillars. If you don't know "
                       "it, just say so and I'll cast a three-pillar reading")

        text = ""
        if have:
            text += "I have " + " and ".join(have) + ". "
        text += ("Now I just need " if have else
                 "To cast your Four Pillars, I'll need ") + " and ".join(ask) + "."
        if not gender_known:
            text += (" If you'd like your decade luck cycles too, tell me "
                     "whether to read them as male or female — the tradition "
                     "calculates their direction from this.")
        return SpecialistReply(
            status="need_input",
            text=text,
            missing=missing,
        )

    if time_unknown:
        hour, minute = 12, 0          # placeholder for the library call only;
                                      # the hour pillar is excluded from output
    else:
        hour, minute = birth_time
    gender = _parse_gender(context.get("gender"))

    chart = calculate_bazi(birth_date.year, birth_date.month, birth_date.day,
                           hour, minute, gender, hour_known=not time_unknown)

    place = context.get("birth_place")
    place_line = f"\nBirth place: {place}" if place else ""
    cycles_note = ("" if gender is not None else
                   "\n(No gender given, so decade luck cycles are omitted — "
                   "invite them to share it if they want the long-term timing.)")

    history = context.get("history", "")
    history_block = f"\nEarlier in the conversation:\n{history}\n" if history else ""

    contents = (
        f'The person asked: "{user_message}"'
        f"{place_line}"
        f"{history_block}"
        f"\n\nTheir calculated Four Pillars chart:\n{_format_chart(chart)}"
        f"{cycles_note}\n\n"
        f"Give the reading, anchored on the Day Master and the elemental balance."
    )

    response = client.models.generate_content(
        model=MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=BAZI_PROMPT,
            temperature=0.9,
        ),
    )
    return SpecialistReply(status="reading", text=response.text)


# --- Quick standalone test (run from repo root) ---------------------------
#     python -m agents.specialists.bazi
if __name__ == "__main__":
    ctx = {"birth_date": "1994-04-25", "birth_time": "14:30",
           "gender": "female", "birth_place": "Taipei, Taiwan"}
    reply = run("What should I focus on in my career over the next decade?", ctx)
    print(f"[{reply.status}]\n{reply.text}")