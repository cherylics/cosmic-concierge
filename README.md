# Cosmic Concierge ✦

Some questions don't have a lookup answer. When you're feeling adrift — unsure which way to turn, caught between two choices, or just trying to make sense of a season of life — **Cosmic Concierge** is a place to pause, get your bearings, and reflect.

A warm front-desk concierge listens to what's really on your mind and points you toward the practice that fits: **Tarot** for a decision in motion, **Western Zodiac** for the patterns in who you are, or **Chinese Bazi (Four Pillars of Destiny / 八字)** for the longer arc of your life. Every reading is grounded in a real, deterministic calculation and then interpreted for your specific question — guidance to reflect on, never a verdict.

Built with Streamlit and Google Gemini for the **Kaggle Vibe Coding Agents Capstone** (Concierge Agents track).

---

## What it does

Four ways in, shown as cards on the landing page:

- **Tarot** — for a specific question or decision happening now. Draws a real three-card spread (78-card deck, upright/reversed) and reads it against your question.
- **Zodiac** — for identity, patterns, and compatibility. Anchored on your sun sign, computed from your birth date.
- **Bazi · 八字** — for your long-term life trajectory. Casts your Four Pillars, Five-Element balance, Day Master, and decade luck cycles (Da Yun) from your exact birth moment.
- **Cosmo** — not sure which you need? Describe the situation and the Concierge routes you to the best-fit practice (or gently redirects if it's really a medical/legal/financial matter).

---

## Design principle: *math by function, meaning by model*

Correctness and creativity are kept strictly separate:

- **Deterministic tools compute the facts.** Card draws, sun-sign lookup, and the entire Four Pillars chart (via `lunar_python`) are computed in plain Python. The model never invents a card, a sign, a pillar, or a date.
- **The model only interprets** the numbers it's handed, in the voice of each practice.

This is why the esoteric math is trustworthy even though the prose is generative.

---

## Architecture

```
                         ┌──────────────────────────────┐
   Streamlit UI  ───────▶│  utils/chat.py  (the bridge)  │
   (app.py)              │  handle_turn(...)             │
                         └───────────────┬──────────────┘
                                         │  builds context from memory,
                                         │  captures birth details,
                                         │  chooses forced vs routed
                                         ▼
                         ┌──────────────────────────────┐
                         │  agents/orchestrator.py       │
                         │  concierge() / route_request()│
                         └───────┬───────────────┬───────┘
                     forced pick │               │ router decision
                                 ▼               ▼
                    ┌────────────────────┐   clarify / out_of_scope
                    │ agents/specialists │   (no specialist runs)
                    │  tarot·zodiac·bazi │
                    └─────────┬──────────┘
                              │ deterministic tool → model interprets
                              ▼
                         SpecialistReply  →  ConciergeResult  →  memory (if a real reading)
```

**How one turn flows**

1. The user picks a practice (or Cosmo) and asks a question. `app.py` calls `chat.handle_turn(user_id, active_agent, message)`.
2. The **bridge** (`utils/chat.py`) opportunistically parses any birth date/time/gender from the message into the memory profile, then builds a `context` dict from the stored profile plus a short recap of recent readings.
3. Routing: a specific card goes **straight to that specialist** (`forced_route`), skipping the router; **Cosmo** calls `route_request()`, where the LLM router returns a structured `RouterDecision`.
4. The specialist runs its deterministic tool, hands the facts to the model, and returns a `SpecialistReply` — either a finished reading or a request for more input.
5. The orchestrator maps that onto a `ConciergeResult` carrying an explicit `status`. The bridge logs to memory **only for completed readings**, renders the markdown to HTML, and returns `(html, route, status)`.
6. `app.py` shows the reply and, after Cosmo routes you somewhere, "sticky-locks" follow-up turns to that specialist.

---

## Project structure

```
cosmic-concierge/
├── app.py                     # Streamlit frontend: landing cards + chat view
├── requirements.txt
├── .gitignore                 # ignores .env, .venv, __pycache__, data/ (user memory)
├── README.md
│
├── assets/                    # landing-page illustrations
│   ├── tarot.png  zodiac.png  bazi.png  cosmic.png
│
├── agents/                    # the agent layer
│   ├── orchestrator.py        # Concierge router + dispatch (concierge / route_request)
│   ├── report.py              # weekly reflection agent (calendar-windowed)
│   └── specialists/
│       ├── tarot.py           # 78-card draw  → interpretation
│       ├── zodiac.py          # sun-sign lookup → interpretation
│       └── bazi.py            # Four Pillars via lunar_python → interpretation
│
└── utils/                     # shared infrastructure
    ├── chat.py                # bridge between the UI and the agent layer
    ├── config.py              # model name + shared genai.Client()
    ├── persona.py             # SHARED_RULES: tone, formatting, safety boundaries
    ├── memory.py              # per-user JSON profiles + reading history
    └── schemas.py             # Pydantic contracts shared across every layer
```

---

## Data contracts (`utils/schemas.py`)

Every layer speaks the same typed language:

- **`Route`** — `Literal["tarot", "zodiac", "bazi", "clarify", "out_of_scope"]`.
- **`TurnStatus`** — `Literal["reading", "need_input", "clarify", "out_of_scope"]`.
- **`RouterDecision`** — the router's choice (`route`, `rationale`, `message_to_user`); generated with `response_schema` so the JSON is always valid.
- **`SpecialistReply`** — what every specialist's `run()` returns: `status` (`reading` / `need_input`), `text`, and `missing` (fields still needed).
- **`ConciergeResult`** — the terminal result of a turn. `status` is **required** (no silent default), and `is_reading` is the single gate memory checks before logging.
- **`WeeklyReport`** — the Report agent's output, with `subject`/`period_start`/`period_end` derived from the same window used to filter, so the header can never claim a range the filter didn't cover.

---

## Safety

Guidance is framed as reflection and entertainment, never prediction or professional advice, at two layers:

- The **router** detects a medical, legal, financial, or self-harm concern dressed up as a fortune question and returns `out_of_scope` — acknowledging the real issue and pointing to a qualified professional instead of routing to a reading.
- **`SHARED_RULES`** (appended to every specialist's system prompt) reinforces those boundaries in the reading itself.

### Intentionally out of scope

Cosmic Concierge is for reflection, not for decisions that need a qualified professional. By design, it will **not**:

- give **financial or investment advice** — what to buy, sell, or put your money into;
- offer **medical guidance, diagnosis, or physical treatment**;
- give **legal advice**;
- promise **certainty about the future** or anyone's fate.

When a question is really about one of these — even when it arrives dressed as a fortune question ("will my chest pain go away?", "should I move my savings into this stock?") — the Concierge names the real concern and points you toward a qualified professional or someone you trust, rather than producing a reading.

---

## Getting started

Requires Python 3.10+ and a Google Gemini API key.

```bash
# 1. clone
git clone https://github.com/cherylics/cosmic-concierge.git
cd cosmic-concierge

# 2. virtual environment
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 3. dependencies
pip install -r requirements.txt

# 4. API key — create a .env file in the repo root (it is gitignored):
echo "GEMINI_API_KEY=your_key_here" > .env

# 5. run
streamlit run app.py
```

The model is set in one place (`utils/config.py`, currently `gemini-2.5-flash`). The router runs at low temperature for consistent routing; the specialists run hotter so readings feel alive.

---

## Testing

Each agent has a standalone self-test you can run from the repo root (these make live model calls):

```bash
python -m agents.specialists.tarot      # a tarot reading
python -m agents.specialists.zodiac     # asks for birth data, then reads
python -m agents.specialists.bazi       # a full Four Pillars reading
python -m agents.orchestrator           # routes several sample questions
python -m agents.report                 # a weekly reflection for a demo user
```

The deterministic pieces (card draw, sun-sign lookup, Four Pillars math, report windowing) are pure functions and can be tested without any API calls.

---

## Team & status

- **Agent intelligence layer** (router, specialists, memory contract, report) — Mengci Duan.
- **Frontend, bridge/memory integration, packaging** — Yichen Li.

The orchestration layer is fully wired to the frontend; the four practices, routing, birth-detail capture, per-session memory, and safety redirects all work end to end. The **weekly Report agent is implemented in the agent layer but not yet surfaced in the UI** — it's ready to be triggered from a button or a scheduled job. Per-user memory is currently scoped to a browser session (an anonymous `user_id`); a stable identity would enable returning-user history and richer weekly reports.