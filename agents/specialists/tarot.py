# agents/specialists/tarot.py
import os
import sys

# Add project root to sys.path so python can find 'utils' when this script is run directly
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import random

from google.genai import types

from utils.config import client, MODEL
from utils.persona import SHARED_RULES

SPECIALIST_NAME = "tarot"


# --- The deck: a real 78-card deck ----------------------------------------

MAJOR_ARCANA = [
    "The Fool", "The Magician", "The High Priestess", "The Empress",
    "The Emperor", "The Hierophant", "The Lovers", "The Chariot",
    "Strength", "The Hermit", "Wheel of Fortune", "Justice",
    "The Hanged Man", "Death", "Temperance", "The Devil",
    "The Tower", "The Star", "The Moon", "The Sun", "Judgement", "The World",
]
SUITS = ["Wands", "Cups", "Swords", "Pentacles"]
RANKS = ["Ace", "Two", "Three", "Four", "Five", "Six", "Seven",
         "Eight", "Nine", "Ten", "Page", "Knight", "Queen", "King"]
MINOR_ARCANA = [f"{rank} of {suit}" for suit in SUITS for rank in RANKS]
FULL_DECK = MAJOR_ARCANA + MINOR_ARCANA   # 78 cards


def draw_cards(n: int = 3) -> list[str]:
    """An honest draw: real randomness, each card upright or reversed.

    This is the 'tool'. The model never picks cards — it only reads the
    cards that chance dealt, exactly like a real spread.
    """
    drawn = random.sample(FULL_DECK, n)   # no repeats, like a shuffled deck
    return [f"{card} ({'reversed' if random.random() < 0.5 else 'upright'})"
            for card in drawn]


# --- The reader's voice (tarot-specific only; shared rules appended) -------

TAROT_PERSONA = """
You are an insightful Tarot reader at Cosmic Concierge. You are skilled in
drawing and interpreting Tarot cards, reading spreads, and applying card
symbolism to the user's specific life questions.

# How to read
You are given the user's question and a three-card spread. The positions are:
  1. The situation — the heart of what's happening now
  2. The guidance — the energy or attitude to lean into
  3. Where it may lead — a possible direction, not a fixed fate

Interpret the ACTUAL cards you are given (respect upright/reversed) in light of
THIS person's question. Weave the three cards into one coherent story — don't
just define each card in isolation. Speak directly to the person, and keep it
to 3-4 short paragraphs.
"""

TAROT_PROMPT = TAROT_PERSONA + SHARED_RULES


# --- The specialist interface (matches the stub) --------------------------

def run(user_message: str, context: dict) -> str:
    """Draw a spread and return the reading. Called by the orchestrator."""
    # Directive 1: for tarot we need a focus area. If the input is too thin to
    # read on, ask before drawing rather than guessing.
    if len(user_message.strip()) < 8 and not context.get("focus_area"):
        return ("Before I draw your cards — what area of life would you like to "
                "focus on? Love, career, a specific decision, or something else?")

    cards = draw_cards(3)
    positions = ["The situation", "The guidance", "Where it may lead"]
    spread = "\n".join(f"  {pos}: {card}"
                       for pos, card in zip(positions, cards))

    history = context.get("history", "")
    history_block = f"\nEarlier in the conversation:\n{history}\n" if history else ""

    contents = (
        f'The user wants to focus on: "{user_message}"\n'
        f"{history_block}"
        f"\nThe three cards drawn:\n{spread}\n\n"
        f"Give the reading."
    )

    response = client.models.generate_content(
        model=MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=TAROT_PROMPT,
            temperature=0.9,   # high: readings should feel varied and alive
        ),
    )
    return response.text


# --- Quick standalone test (run from repo root) ---------------------------
#     python -m agents.specialists.tarot
if __name__ == "__main__":
    print(run("Should I take the new job offer or stay where I am?", {}))