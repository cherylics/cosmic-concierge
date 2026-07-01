# agents/orchestrator.py - The master "Concierge" router agent
import os
import sys

# Add project root to sys.path so `utils` / `agents` import cleanly whether this
# file is run directly, run via `python -m agents.orchestrator`, or imported by
# app.py. This is the fix for the "cannot find module 'utils'" error.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Convenience: when this file is executed DIRECTLY (python agents/orchestrator.py),
# re-exec under the project venv so third-party deps (google-genai, lunar_python,
# pydantic) resolve without manually activating it first.
#
# This is guarded by __name__ == "__main__" and placed BEFORE the third-party
# imports on purpose. That guard is the whole point: an unguarded, top-level
# os.execv fires on IMPORT too, so `from agents.orchestrator import concierge`
# inside app.py could replace the running Streamlit process mid-import. Guarded
# here, it only ever runs on a direct invocation, never on import.
if __name__ == "__main__":
    _venv_python = os.path.abspath(os.path.join(project_root, ".venv", "bin", "python"))
    if os.path.exists(_venv_python) and sys.executable != _venv_python:
        os.execv(_venv_python, [_venv_python] + sys.argv)

from typing import Optional
from google.genai import types

from utils.config import client, MODEL
from utils.schemas import RouterDecision, ConciergeResult
from agents.specialists import tarot, zodiac, bazi


CONCIERGE_ROUTER_PROMPT = """
You are the Concierge — the warm, perceptive front desk of Cosmic Concierge,
a personal guidance service. You do not give readings yourself. Your only job
is to listen to what the person is really dealing with and route them to the
specialist best suited to help.

# Your specialists

- tarot — Best for a SPECIFIC question or decision happening NOW. A crossroads,
  a "should I…", a situation in motion, an emotional knot they want insight on.
  Tarot is moment-in-time and question-driven. No birth details needed.

- zodiac — Best for questions about IDENTITY, PATTERNS, and PEOPLE over time.
  "Why am I like this", personality, compatibility, relationship dynamics,
  long-cycle timing. Needs the person's birth date (and ideally time/place).

- bazi — Best for the person's OWN long-term life trajectory and destiny chart.
  Career arc, life-stage luck cycles, what they're naturally built for, and
  elemental balance over years. Derived from the FULL birth detail — date, and
  ideally exact time and place. Single-person and long-horizon, not relational.

# How to decide

1. Identify the person's underlying need, not just keywords. "My ex keeps
   texting me" is a present decision (tarot), but "we never get along, we're
   so different" is about patterns and compatibility (zodiac).
2. If two could fit, pick the PRIMARY one and note the secondary in rationale.
3. If the request is too vague to route confidently, choose "clarify" and ask
   exactly ONE friendly question that would settle it.
4. If the request needs zodiac but no birth date was given, still route to
   zodiac — the specialist will collect it. Don't ask for it yourself.
5. Zodiac vs bazi: both use birth data. Route to ZODIAC for identity,
   personality, and compatibility WITH OTHERS. Route to BAZI for the person's
   OWN long-term path, career trajectory, and elemental makeup over years.
   Relational → zodiac. Solo and long-horizon → bazi.

# Safety (do this before routing)

If the person is really asking about a medical, legal, financial, or
self-harm matter dressed up as a fortune question (e.g. "will my chest pain
go away", "should I put my savings in this stock"), DO NOT route to a
specialist for a prediction. Choose "out_of_scope", gently acknowledge the
real concern, and suggest they speak to a qualified professional or trusted
person. Never promise certainty about the future or anyone's fate — frame
guidance as reflection, not prophecy.

# Output

Respond with ONLY a JSON object, no markdown, no extra text:

{
  "route": "tarot" | "zodiac" | "bazi" | "clarify" | "out_of_scope",
  "rationale": "one short sentence explaining your choice (for logs)",
  "message_to_user": "what the Concierge says: a warm handoff line for a
   specialist route, the single question for 'clarify', or the gentle
   redirect for 'out_of_scope'"
}
""".strip()


# Maps a route to the specialist that handles it.
# Every specialist exposes: run(user_message: str, context: dict) -> str
SPECIALISTS = {
    "tarot": tarot.run,
    "zodiac": zodiac.run,
    "bazi": bazi.run,
}

# The routes that never reach a specialist.
_NON_SPECIALIST_ROUTES = ("clarify", "out_of_scope")

# A single source of truth for the fallback when we can't route confidently.
_CLARIFY_FALLBACK = ("I want to point you to the right guide — could you tell me "
                     "a bit more about what's on your mind?")


# --- Routing ---------------------------------------------------------------

def route_request(user_message: str) -> RouterDecision:
    """Ask the Concierge which specialist (if any) should handle this."""
    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=CONCIERGE_ROUTER_PROMPT,
                response_mime_type="application/json",
                response_schema=RouterDecision,   # guarantees valid JSON
                temperature=0.3,                  # routing wants consistency
            ),
        )
        return RouterDecision.model_validate_json(response.text)
    except Exception as e:
        # Fail safe: never crash the app or blind-guess a route.
        print(f"DEBUG: Router error caught: {e}", file=sys.stderr)
        return RouterDecision(
            route="clarify",
            rationale=f"router error: {e}",
            message_to_user=_CLARIFY_FALLBACK,
        )


# --- Dispatch / handoff ----------------------------------------------------

def _result_from_reply(route: str, reply, handoff: Optional[str]) -> ConciergeResult:
    """Map a specialist's SpecialistReply onto a ConciergeResult.

    `handoff` is the router's warm intro line for a reading; it's None when the
    user picked the practice directly (no routing happened), in which case the
    reading stands on its own.
    """
    if reply.status == "need_input":
        return ConciergeResult(
            route=route,
            status="need_input",
            concierge_message=reply.text,          # show the specialist's question
            reading=None,
            missing=reply.missing,
        )
    return ConciergeResult(
        route=route,
        status="reading",
        concierge_message=handoff or "",           # empty for a direct practice pick
        reading=reply.text,
    )


def concierge(user_message: str, context: Optional[dict] = None,
              forced_route: Optional[str] = None) -> ConciergeResult:
    """Full front-desk turn: route, then hand off to a specialist if needed.

    `forced_route` lets the UI send the user straight to a chosen specialist
    (the Tarot/Zodiac/Bazi cards) and skip the router. When it isn't a known
    specialist (e.g. the "cosmic" card, or None), the router decides as usual.
    """
    context = context or {}

    # Direct practice pick from the UI -> skip the router entirely.
    if forced_route in SPECIALISTS:
        reply = SPECIALISTS[forced_route](user_message, context)
        return _result_from_reply(forced_route, reply, handoff=None)

    decision = route_request(user_message)

    # clarify and out_of_scope never reach a specialist. For these the status
    # IS the route ("clarify" / "out_of_scope"), and there is no reading.
    if decision.route in _NON_SPECIALIST_ROUTES:
        return ConciergeResult(
            route=decision.route,
            status=decision.route,
            concierge_message=decision.message_to_user,
            reading=None,
        )

    # Defensive: RouterDecision.route SHOULD be a Literal in utils/schemas.py,
    # which prevents any out-of-set value at the schema layer. This guard is the
    # belt to that suspenders — if a bad route ever slips through, we degrade to
    # a clarify instead of a raw KeyError that would crash the turn.
    specialist = SPECIALISTS.get(decision.route)
    if specialist is None:
        return ConciergeResult(
            route="clarify",
            status="clarify",
            concierge_message=_CLARIFY_FALLBACK,
            reading=None,
        )

    # The specialist returns a SpecialistReply — either a finished reading or a
    # request for more input. Map the two onto a ConciergeResult so the app can
    # switch on `status` and memory can log only completed readings.
    reply = specialist(user_message, context)
    return _result_from_reply(decision.route, reply, handoff=decision.message_to_user)


# --- Quick manual test (run from repo root: python -m agents.orchestrator) --
if __name__ == "__main__":
    import time
    ctx = {"birth_date": "1994-04-25", "birth_time": "14:30", "gender": "female"}
    for i, msg in enumerate([
        "Should I text my ex back? I keep going back and forth.",
        "What's my career path look like over the next ten years?",
        "Why do my partner and I clash so much, we're so different?",
        "I've had chest pains for a week, will they go away?",
    ]):
        if i > 0:
            print("\nWaiting 12 seconds to avoid rate limits...")
            time.sleep(12)

        result = concierge(msg, ctx)
        print(f"\n[{result.route}/{result.status}] {result.concierge_message}")
        if result.missing:
            print(f"  missing: {result.missing}")
        if result.reading:
            print(f"  reading: {result.reading[:120]}...")