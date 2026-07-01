# memory.py - Handles passing conversation context between agents
# utils/memory.py - long-term memory: user profiles + reading history
import os
import sys

# Auto-execute using the virtual environment python if it exists and we aren't using it
venv_python = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".venv", "bin", "python"))
if os.path.exists(venv_python) and sys.executable != venv_python:
    os.execv(venv_python, [venv_python] + sys.argv)

# Add project root to sys.path to allow running the script directly
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Kept out of git — add `data/` to .gitignore.
MEMORY_DIR = Path(os.environ.get("MEMORY_DIR", "data/memory"))

# Which profile fields the specialists actually consume (see each run()).
PROFILE_FIELDS = ("birth_date", "birth_time", "gender", "birth_place")


def _user_path(user_id: str) -> Path:
    safe = "".join(c for c in user_id if c.isalnum() or c in ("-", "_")) or "anon"
    return MEMORY_DIR / f"{safe}.json"


def _empty() -> dict:
    return {"profile": {}, "readings": []}


def load_user(user_id: str) -> dict:
    """Return the full record for a user (empty scaffold if none yet)."""
    path = _user_path(user_id)
    if not path.exists():
        return _empty()
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        data.setdefault("profile", {})
        data.setdefault("readings", [])
        return data
    except (json.JSONDecodeError, OSError):
        return _empty()   # corrupt file shouldn't crash the app


def _save_user(user_id: str, record: dict) -> None:
    """Atomic write: temp file then rename, so a crash never truncates memory."""
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    path = _user_path(user_id)
    fd, tmp = tempfile.mkstemp(dir=MEMORY_DIR, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


# --- Profile ---------------------------------------------------------------

def get_profile(user_id: str) -> dict:
    return load_user(user_id)["profile"]


def update_profile(user_id: str, **fields) -> dict:
    """Set/merge profile fields (birth_date, birth_time, gender, birth_place).

    Only known, non-empty fields are stored. Returns the updated profile.
    """
    record = load_user(user_id)
    for key, value in fields.items():
        if key in PROFILE_FIELDS and value not in (None, ""):
            record["profile"][key] = value
    _save_user(user_id, record)
    return record["profile"]


def has_birth_data(user_id: str) -> bool:
    """True once we have at least a birth date (enough for zodiac)."""
    return bool(get_profile(user_id).get("birth_date"))


# --- Readings log ----------------------------------------------------------

def add_reading(user_id: str, route: str, question: str, reading: str) -> None:
    """Append one reading to the user's history."""
    if not reading:
        return
    record = load_user(user_id)
    record["readings"].append({
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "route": route,
        "question": question,
        "reading": reading,
    })
    _save_user(user_id, record)


def recent_readings(user_id: str, n: int = 3) -> list[dict]:
    """The n most recent readings, newest last."""
    return load_user(user_id)["readings"][-n:]


def all_readings(user_id: str) -> list[dict]:
    """Full history — the Report agent uses this for the weekly report."""
    return load_user(user_id)["readings"]


# --- The bridge: build the context dict the specialists read ---------------

def _history_summary(readings: list[dict], max_chars: int = 200) -> str:
    """Compact, human-readable recap injected into specialist prompts."""
    lines = []
    for r in readings:
        day = r["ts"][:10]
        snippet = " ".join(r["reading"].split())[:max_chars]
        lines.append(f'- {day} ({r["route"]}) asked "{r["question"]}" → {snippet}…')
    return "\n".join(lines)


def build_context(user_id: str, extra: Optional[dict] = None,
                  history_n: int = 3) -> dict:
    """Assemble the context passed into concierge()/specialists.

    Merges the stored profile, a short recap of recent readings, and any
    per-turn extras (e.g. a focus_area from a form). `extra` wins on conflict.
    """
    record = load_user(user_id)
    ctx = dict(record["profile"])              # birth_date, birth_time, ...
    recent = record["readings"][-history_n:]
    if recent:
        ctx["history"] = _history_summary(recent)
    if extra:
        ctx.update({k: v for k, v in extra.items() if v not in (None, "")})
    return ctx