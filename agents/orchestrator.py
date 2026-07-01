# orchestrator.py - The master "Concierge" router agent
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

# orchestrator.py - The master "Concierge" router agent
import os
import sys

# Auto-execute using the virtual environment python if it exists and we aren't using it
venv_python = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".venv", "bin", "python"))
if os.path.exists(venv_python) and sys.executable != venv_python:
    os.execv(venv_python, [venv_python] + sys.argv)

from typing import Literal, Optional

# Add project root to sys.path to allow running the script directly
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from dotenv import load_dotenv
from pydantic import BaseModel
from google import genai
from google.genai import types

from agents.specialists import tarot, zodiac, bazi

load_dotenv()  # reads GEMINI_API_KEY from your .env

# Use whatever current flash model AI Studio gives you.
# gemini-2.5-flash is reliable on the free tier; newer gemini-3.x flash also works.
MODEL = "gemini-2.5-flash"

client = genai.Client()  # picks up GEMINI_API_KEY from the environment


# --- The shared contract (lock this with Person B) -------------------------

class RouterDecision(BaseModel):
    route: Literal["tarot", "zodiac", "bazi", "clarify", "out_of_scope"]
    rationale: str
    message_to_user: str


class ConciergeResult(BaseModel):
    route: str
    concierge_message: str          # the warm handoff / clarify question / redirect
    reading: Optional[str] = None   # the specialist's output, or None


# Maps a route to the specialist that handles it.
# Every specialist must expose: run(user_message: str, context: dict) -> str
SPECIALISTS = {
    "tarot": tarot.run,
    "zodiac": zodiac.run,
    "bazi": bazi.run,
}


# CONCIERGE_ROUTER_PROMPT = """ ... your prompt stays here ... """


# --- Step 2: routing -------------------------------------------------------

def route_request(user_message: str) -> RouterDecision:
    """Ask the Concierge which specialist (if any) should handle this."""
    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=CONCIERGE_ROUTER_PROMPT,
                response_mime_type="application/json",
                response_schema=RouterDecision,  # guarantees valid JSON
                temperature=0.3,                 # routing wants consistency, not flair
            ),
        )
        return RouterDecision.model_validate_json(response.text)
    except Exception as e:
        # Fail safe: if the model or network hiccups, ask a clarifying question
        # rather than crashing the app or guessing a route.
        return RouterDecision(
            route="clarify",
            rationale=f"router error: {e}",
            message_to_user="I want to point you to the right guide — could you tell me a bit more about what's on your mind?",
        )


# --- Step 3: dispatch / handoff -------------------------------------------

def concierge(user_message: str, context: Optional[dict] = None) -> ConciergeResult:
    """Full front-desk turn: route, then hand off to a specialist if appropriate."""
    context = context or {}
    decision = route_request(user_message)

    # clarify and out_of_scope never reach a specialist — the Concierge handles them.
    if decision.route in ("clarify", "out_of_scope"):
        return ConciergeResult(
            route=decision.route,
            concierge_message=decision.message_to_user,
            reading=None,
        )

    specialist_fn = SPECIALISTS[decision.route]
    reading = specialist_fn(user_message, context)
    return ConciergeResult(
        route=decision.route,
        concierge_message=decision.message_to_user,
        reading=reading,
    )


# --- Quick manual test (run: python -m orchestrator) -----------------------

if __name__ == "__main__":
    for msg in [
        "Should I text my ex back? I keep going back and forth.",   # -> tarot
        "What's my career path look like over the next ten years?", # -> bazi
        "Why do my partner and I clash so much, we're so different",# -> zodiac
        "I've had chest pains for a week, will they go away?",      # -> out_of_scope
    ]:
        result = concierge(msg)
        print(f"\n[{result.route}] {result.concierge_message}")
        if result.reading:
            print(f"  reading: {result.reading}")