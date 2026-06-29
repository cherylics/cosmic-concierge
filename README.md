# Cosmic Concierge ✦

Welcome to **Cosmic Concierge**, a wide-layout Streamlit application providing multi-agent esoteric readings: Tarot, Zodiac, and Bazi (Four Pillars of Destiny).

---

## 📁 Project Structure

```
cosmic-concierge/
├── .gitignore               # Ignores __pycache__, .env, and local IDE configs
├── README.md                # Project overview and installation instructions
├── requirements.txt         # Python dependencies
├── app.py                   # Main Streamlit frontend application
│
├── assets/                  # Illustrations used on the landing page
│   ├── tarot.png
│   ├── zodiac.png
│   ├── bazi.png
│   └── cosmic.png
│
├── agents/                  # The Multi-Agent Orchestration Layer
│   ├── __init__.py
│   ├── orchestrator.py      # Master "Concierge" router agent
│   │
│   └── specialists/         # Individual esoteric expert agents
│       ├── __init__.py
│       ├── tarot.py         # Tarot reading systems & logic
│       ├── zodiac.py        # Astrology/Zodiac prompts & logic
│       └── bazi.py          # Chinese Bazi prompts & logic (replaces feng_shui)
│
└── utils/                   # Shared helper utilities
    ├── __init__.py
    └── memory.py            # Passes conversation context between agents
```

---

## 🚀 Getting Started

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the Streamlit App**:
   ```bash
   streamlit run app.py
   ```

---

## 📢 Notes for Teammates

If you are working on the **Orchestration Layer** or **Specialist Agents**, please keep these updates in mind:

1. **Specialist Rename (Feng Shui ➔ Bazi)**
   * We switched the Feng Shui agent to a **Bazi Agent** (Chinese destiny reading).
   * The file has been renamed to `agents/specialists/bazi.py`. Write Bazi prompts/logic here.

2. **Integration Hooks (Session State & Router)**
   * **Selected Agent**: The chosen practice key is stored in `st.session_state.active_agent` (`"tarot"`, `"zodiac"`, `"bazi"`, or `"cosmic"`).
   * **Chat History**: Initialized in `st.session_state.chat_history` as a list of dictionaries: `[{"role": "user/assistant", "content": "..."}]`.
   * **Connecting Orchestrator**: The frontend currently appends placeholder text to the chat history when a message is sent. We will wire up the routing layer in `app.py` where the placeholder response is generated.