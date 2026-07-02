import streamlit as st
import base64
import uuid
from pathlib import Path

from utils.chat import handle_turn

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Cosmic Concierge",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="collapsed",
)


# ── Helpers ──────────────────────────────────────────────────────────────────
def img_to_base64(path: str) -> str:
    return base64.b64encode(Path(path).read_bytes()).decode()


ASSET_DIR = Path(__file__).parent / "assets"
TAROT_B64 = img_to_base64(ASSET_DIR / "tarot.png")
ZODIAC_B64 = img_to_base64(ASSET_DIR / "zodiac.png")
BAZI_B64 = img_to_base64(ASSET_DIR / "bazi.png")
COSMIC_B64 = img_to_base64(ASSET_DIR / "cosmic.png")

# ── Practice data ────────────────────────────────────────────────────────────
PRACTICES = {
    "tarot": {
        "title": "Tarot",
        "img": TAROT_B64,
        "label": "Tarot",
        "hover": (
            "Draw from a 78-card deck to illuminate "
            "patterns in your past, present, and future."
        ),
        "greeting": (
            "Welcome to your Tarot reading ✦\n\n"
            "I'll draw cards and interpret their meaning in the context "
            "of your question. What would you like guidance on?"
        ),
    },
    "zodiac": {
        "title": "Zodiac",
        "img": ZODIAC_B64,
        "label": "Zodiac",
        "hover": (
            "Explore how planetary transits and your "
            "natal chart shape your personality and path."
        ),
        "greeting": (
            "Welcome to your Zodiac reading ✦\n\n"
            "I can interpret your birth chart, current transits, "
            "and astrological themes. What's your sign, or share "
            "your birth details for a deeper look?"
        ),
    },
    "bazi": {
        "title": "Bazi · 八字",
        "img": BAZI_B64,
        "label": "Bazi · 八字",
        "hover": (
            "Decode the Four Pillars of Destiny from your "
            "birth year, month, day, and hour."
        ),
        "greeting": (
            "Welcome to your Bazi reading ✦\n\n"
            "I'll decode your Four Pillars of Destiny — the interplay "
            "of Wood, Fire, Earth, Metal, and Water in your life. "
            "Please share your birth date and time to begin."
        ),
    },
    "cosmic": {
        "title": "Cosmic",
        "img": COSMIC_B64,
        "label": "Cosmic",
        "hover": (
            "Tell us what's on your mind and "
            "we'll choose the right reading for you."
        ),
        "greeting": (
            "Welcome to Cosmic Concierge ✦\n\n"
            "Tell me what's on your mind — a relationship, a career "
            "crossroads, a feeling you can't quite name — and I'll "
            "guide you to the cosmic practice that fits best."
        ),
    },
}

# ── Session state ────────────────────────────────────────────────────────────
if "user_id" not in st.session_state:
    st.session_state.user_id = uuid.uuid4().hex
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "active_agent" not in st.session_state:
    st.session_state.active_agent = None
if "selected_card" not in st.session_state:
    st.session_state.selected_card = None


def select_practice(key: str):
    st.session_state.selected_card = key


def switch_practice(key: str):
    if key == "home":
        st.session_state.chat_history = []
        st.session_state.active_agent = None
        st.session_state.selected_card = None
    else:
        st.session_state.active_agent = key
        st.session_state.selected_card = key
        practice = PRACTICES[key]
        st.session_state.chat_history = [
            {"role": "assistant", "content": practice["greeting"]}
        ]


def _run_agent(user_message: str) -> str:
    """Run one turn through the agent layer; degrade gracefully on error."""
    try:
        return handle_turn(
            st.session_state.user_id,
            st.session_state.active_agent,
            user_message,
        )
    except Exception as e:
        return (
            "The cosmos is clouded for a moment — I couldn't complete that "
            "reading. Please try again."
            f"<br><br><span style='opacity:0.6'>({e})</span>"
        )


# ── Styles ───────────────────────────────────────────────────────────────────
selected = st.session_state.selected_card

st.markdown(
    """
    <style>
    /* Hide sidebar */
    section[data-testid="stSidebar"] { display: none !important; }
    [data-testid="stSidebarCollapsedControl"] { display: none !important; }

    /* ---------- Single font ---------- */
    @import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,500;0,600;1,300;1,400&display=swap');

    html, body, [class*="css"],
    .stApp, .stApp *,
    h1, h2, h3, p, span, div, a, li, label, input, textarea, button {
        font-family: 'Cormorant Garamond', Georgia, 'Times New Roman', serif !important;
    }

    /* ---------- Hide header completely ---------- */
    header[data-testid="stHeader"] {
        display: none !important;
    }

    /* ---------- Uniform background ---------- */
    .stApp,
    div[data-testid="stBottomBlockContainer"],
    div[data-testid="stBottom"] {
        background: #faf9f7 !important;
    }

    .block-container {
        padding-top: 0 !important;
        padding-bottom: 0 !important;
        max-width: 900px !important;
    }

    /* ---------- Title ---------- */
    .cc-title {
        color: #1a1a1a !important;
        -webkit-text-fill-color: #1a1a1a !important;
        font-weight: 400 !important;
        font-size: 3.2rem !important;
        letter-spacing: 0.04em;
        margin: 0 0 16px 0 !important;
        line-height: 1.1 !important;
        text-align: center;
        background: none !important;
        -webkit-background-clip: unset !important;
    }

    .cc-subtitle {
        font-weight: 300 !important;
        font-size: 1.05rem !important;
        color: #8a857f !important;
        -webkit-text-fill-color: #8a857f !important;
        line-height: 1.8;
        text-align: center;
        margin: 0 auto;
    }

    .cc-divider {
        width: 36px;
        height: 1px;
        background: #c8c3bb;
        margin: 28px auto;
        border: none;
    }

    /* ---------- Prompt line ---------- */
    .reading-prompt {
        font-weight: 400 !important;
        font-style: italic;
        font-size: 1.35rem !important;
        color: #5c574f !important;
        -webkit-text-fill-color: #5c574f !important;
        text-align: center;
        margin: 0 0 32px 0;
    }

    /* ---------- Card grid ---------- */
    .card-grid {
        display: flex;
        gap: 24px;
        justify-content: center;
        flex-wrap: wrap;
        max-width: 860px;
        margin: 0 auto;
    }

    /* Position column wrapper relatively to anchor absolute overlay buttons */
    div[data-testid="column"], .stColumn, [class*="stColumn"] {
        position: relative !important;
    }

    /* Absolute overlay container for the button (removed from normal flow to prevent pushing layout) */
    div[data-testid="column"] div.element-container:first-child,
    .stColumn div.element-container:first-child,
    [class*="stColumn"] div.element-container:first-child {
        height: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
        overflow: visible !important;
    }

    /* Make the button fill the overlay completely and make it completely invisible */
    div[data-testid="column"] button,
    .stColumn button,
    [class*="stColumn"] button,
    div[data-testid="column"] [data-testid="baseButton-secondary"],
    .stColumn [data-testid="baseButton-secondary"] {
        position: absolute !important;
        top: 0 !important;
        left: 0 !important;
        width: 100% !important;
        height: 240px !important;
        z-index: 9999 !important;
        background: transparent !important;
        background-color: transparent !important;
        border: none !important;
        border-color: transparent !important;
        color: transparent !important;
        -webkit-text-fill-color: transparent !important;
        box-shadow: none !important;
        outline: none !important;
        cursor: pointer !important;
        padding: 0 !important;
        margin: 0 !important;
    }

    /* Prevent any hover/focus outlines or backgrounds from Streamlit theme */
    div[data-testid="column"] button:hover,
    div[data-testid="column"] button:focus,
    div[data-testid="column"] button:active,
    div[data-testid="column"] button:focus-visible,
    .stColumn button:hover,
    .stColumn button:focus,
    .stColumn button:active,
    .stColumn button:focus-visible,
    div[data-testid="column"] [data-testid="baseButton-secondary"]:hover,
    .stColumn [data-testid="baseButton-secondary"]:hover {
        background: transparent !important;
        background-color: transparent !important;
        border: none !important;
        border-color: transparent !important;
        color: transparent !important;
        -webkit-text-fill-color: transparent !important;
        box-shadow: none !important;
        outline: none !important;
    }

    .card-visual {
        width: 100%;
        max-width: 185px;
        text-align: center;
        transition: transform 0.3s ease;
        margin: 0 auto;
    }

    /* Hover animations triggered by hovering anywhere on the column */
    div[data-testid="column"]:hover .card-visual,
    .stColumn:hover .card-visual,
    [class*="stColumn"]:hover .card-visual {
        transform: translateY(-6px) !important;
    }

    .card-visual img {
        width: 100%;
        aspect-ratio: 1;
        object-fit: cover;
        border-radius: 16px;
        border: 1px solid #e8e4de;
        box-shadow: 0 2px 16px rgba(0,0,0,0.04);
        transition: box-shadow 0.3s ease, border-color 0.3s ease,
                    filter 0.4s ease, opacity 0.4s ease;
    }
    div[data-testid="column"]:hover .card-visual img,
    .stColumn:hover .card-visual img,
    [class*="stColumn"]:hover .card-visual img {
        box-shadow: 0 8px 32px rgba(0,0,0,0.10) !important;
        border-color: #c8c3bb !important;
    }

    .card-visual .card-label {
        font-size: 1.15rem !important;
        font-weight: 500 !important;
        color: #3a3a3a !important;
        -webkit-text-fill-color: #3a3a3a !important;
        margin-top: 10px;
    }

    .card-visual .card-desc {
        font-weight: 300 !important;
        font-size: 0.82rem !important;
        color: #7a756d !important;
        -webkit-text-fill-color: #7a756d !important;
        line-height: 1.55;
        margin-top: 6px;
        max-height: 0;
        overflow: hidden;
        opacity: 0;
        transition: max-height 0.4s ease, opacity 0.3s ease;
    }
    div[data-testid="column"]:hover .card-visual .card-desc,
    .stColumn:hover .card-visual .card-desc,
    [class*="stColumn"]:hover .card-visual .card-desc {
        max-height: 120px !important;
        opacity: 1 !important;
    }

    /* Grayed-out (removed pointer-events: none to keep clickable) */
    .card-visual.grayed img {
        filter: grayscale(100%);
        opacity: 0.3;
    }
    .card-visual.grayed .card-label {
        color: #c0c0c0 !important;
        -webkit-text-fill-color: #c0c0c0 !important;
    }

    /* Selected — gold accent */
    .card-visual.selected img {
        border-color: #b8a88a;
        box-shadow: 0 4px 24px rgba(184, 168, 138, 0.25);
    }

    /* ---------- Prompt area ---------- */
    .mind-prompt {
        font-weight: 400 !important;
        font-style: italic;
        font-size: 1.15rem !important;
        color: #5c574f !important;
        -webkit-text-fill-color: #5c574f !important;
        text-align: center;
        margin: 8px 0 4px 0;
    }

    /* ---------- Chat ---------- */
    .chat-area {
        max-width: 620px;
        margin: 0 auto;
        padding: 28px 0 120px 0;
    }
    .msg-row {
        display: flex;
        gap: 12px;
        margin-bottom: 20px;
        animation: fadeIn 0.4s ease;
        scroll-margin-top: 150px; /* Offset scroll position by 150px to keep clear of fixed header */
    }
    .msg-row.user { flex-direction: row-reverse; }

    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(8px); }
        to   { opacity: 1; transform: translateY(0); }
    }

    .msg-avatar {
        width: 36px; height: 36px;
        border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        font-size: 16px;
        flex-shrink: 0;
    }
    .msg-avatar.assistant { background: #1a1a1a; color: #faf9f7; }
    .msg-avatar.user      { background: #e8e4de; color: #5c574f; }

    .msg-bubble {
        border-radius: 18px;
        padding: 14px 20px;
        max-width: 75%;
        font-size: 1rem !important;
        line-height: 1.65;
        font-weight: 300 !important;
    }
    .msg-bubble.assistant {
        background: #ffffff;
        border: 1px solid #ebe8e3;
        color: #2c2c2c !important;
        -webkit-text-fill-color: #2c2c2c !important;
    }
    .msg-bubble.user {
        background: #1a1a1a;
        color: #f5f4f2 !important;
        -webkit-text-fill-color: #f5f4f2 !important;
    }

    .chat-header-text {
        font-weight: 400 !important;
        font-size: 2rem !important;
        letter-spacing: 0.04em;
        color: #1a1a1a !important;
        -webkit-text-fill-color: #1a1a1a !important;
        margin: 0 !important;
        text-align: center;
    }
    .chat-divider {
        width: 36px;
        height: 1px;
        background: #c8c3bb;
        margin: 12px auto 0 auto;
    }

    /* ---------- Bottom Section (inside stBottom, holds chat input) ---------- */
    div[data-testid="stBottom"] {
        background: #faf9f7 !important;
        border-top: 1px solid #e8e4de !important;
        padding: 12px 0 16px 0 !important;
        z-index: 99999 !important;
    }
    div[data-testid="stBottomBlockContainer"] {
        padding-bottom: 80px !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ══════════════════════════════════════════════════════════════════════════════
# LANDING VIEW
# ══════════════════════════════════════════════════════════════════════════════
if not st.session_state.chat_history:

    if selected is None:
        st.markdown("<div style='height: 8vh'></div>", unsafe_allow_html=True)
    else:
        st.markdown("<div style='height: 3vh'></div>", unsafe_allow_html=True)

    # ── Header ───────────────────────────────────────────────────────────
    st.markdown(
        '<h1 class="cc-title">Cosmic Concierge</h1>',
        unsafe_allow_html=True,
    )
    
    if selected is None:
        st.markdown(
            """
            <p class="cc-subtitle">
                Awaken your inner power through the cosmic practice you need.<br>
                The universe is already by your side.
            </p>
            <div class="cc-divider"></div>
            """,
            unsafe_allow_html=True,
        )
        st.markdown(
            '<p class="reading-prompt">Which type of reading would you like to get?</p>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown('<div style="height: 16px;"></div>', unsafe_allow_html=True)

    # ── Practice cards (Streamlit columns, independent markdown blocks) ──
    cols = st.columns(4, gap="medium")

    for col_idx, (key, practice) in enumerate(PRACTICES.items()):
        if selected is None:
            cls = ""
        elif selected == key:
            cls = "selected"
        else:
            cls = "grayed"

        with cols[col_idx]:
            # Always render the invisible overlay button to capture click callback
            st.button(
                " ",
                key=f"pick_{key}",
                on_click=select_practice,
                args=(key,),
                use_container_width=True,
            )

            # Render the styled visual card beneath it
            st.markdown(
                f"""
                <div class="card-visual {cls}">
                    <img src="data:image/png;base64,{practice['img']}" alt="{practice['label']}">
                    <div class="card-label">{practice['label']}</div>
                    <div class="card-desc">{practice['hover']}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # ── Text input after card selection ──────────────────────────────────
    if selected:
        st.markdown("<div style='height: 16px'></div>", unsafe_allow_html=True)
        st.markdown(
            '<p class="mind-prompt">✦ What\'s on your mind?</p>',
            unsafe_allow_html=True,
        )

        user_text = st.text_input(
            "What's on your mind?",
            placeholder="Share what you'd like guidance on …",
            label_visibility="collapsed",
        )

        if user_text:
            practice = PRACTICES[selected]
            st.session_state.active_agent = selected
            st.session_state.chat_history = [
                {"role": "assistant", "content": practice["greeting"]},
                {"role": "user", "content": user_text},
            ]
            with st.spinner("Consulting the cosmos…"):
                reply_html = _run_agent(user_text)
            st.session_state.chat_history.append(
                {"role": "assistant", "content": reply_html}
            )
            st.session_state.selected_card = None
            st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# CHAT VIEW
# ══════════════════════════════════════════════════════════════════════════════
else:
    agent_name = PRACTICES.get(
        st.session_state.active_agent, {}
    ).get("title", "Cosmic Concierge")

    # Scoped stylesheet for CHAT VIEW
    st.markdown(
        """
        <style>
        /* Fixed header for the chat session - stays persisted during scrolling */
        .sticky-header-container {
            position: fixed !important;
            top: 0 !important;
            left: 0 !important;
            right: 0 !important;
            background: #faf9f7 !important;
            z-index: 99999 !important;
            padding: 20px 0 0 0 !important;
            text-align: center !important;
            width: 100% !important;
            max-width: 900px !important;
            margin: 0 auto !important;
            height: 60px !important;
        }
        
        /* Fix the horizontal columns block right beneath the header text */
        div[data-testid="stHorizontalBlock"] {
            position: fixed !important;
            top: 60px !important; /* sits directly below title container */
            left: 0 !important;
            right: 0 !important;
            background: #faf9f7 !important;
            z-index: 99999 !important;
            width: 100% !important;
            max-width: 900px !important;
            margin: 0 auto !important;
            padding: 6px 0 10px 0 !important;
            border-bottom: 1px solid #e8e4de !important;
            height: 60px !important;
        }

        /* Clear Streamlit default container margins/paddings inside fixed header block */
        div[data-testid="stHorizontalBlock"] div.element-container {
            margin: 0 !important;
            padding: 0 !important;
        }

        .chat-area {
            max-width: 620px;
            margin: 0 auto;
            padding: 150px 0 40px 0 !important; /* Spacing for fixed header and nav tray */
        }

        /* Center columns in the sticky nav block */
        div[data-testid="stHorizontalBlock"] div[data-testid="column"] {
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            height: 48px !important;
            position: relative !important;
        }

        /* Invisible overlay button stretching over the columns in the top block */
        div[data-testid="stHorizontalBlock"] div[data-testid="column"] div.element-container:first-child {
            height: 0 !important;
            margin: 0 !important;
            padding: 0 !important;
            overflow: visible !important;
        }
        div[data-testid="stHorizontalBlock"] div[data-testid="column"] button {
            position: absolute !important;
            top: 0 !important;
            left: 0 !important;
            width: 100% !important;
            height: 48px !important;
            z-index: 999999 !important;
            background: transparent !important;
            border: none !important;
            color: transparent !important;
            cursor: pointer !important;
            margin: 0 !important;
            padding: 0 !important;
        }
        div[data-testid="stHorizontalBlock"] div[data-testid="column"] button:hover,
        div[data-testid="stHorizontalBlock"] div[data-testid="column"] button:focus,
        div[data-testid="stHorizontalBlock"] div[data-testid="column"] button:active {
            background: transparent !important;
            border: none !important;
            box-shadow: none !important;
            outline: none !important;
        }

        .bottom-tab-card {
            display: flex !important;
            align-items: center !important;
            gap: 8px !important;
            cursor: pointer !important;
            padding: 6px 14px !important;
            border-radius: 20px !important;
            transition: background 0.3s ease;
            border: 1px solid transparent;
            text-align: left;
        }
        .bottom-tab-card:hover {
            background: rgba(232, 228, 222, 0.4) !important;
        }
        .bottom-tab-card.active {
            background: #e8e4de !important;
            border-color: #c8c3bb !important;
        }
        .bottom-tab-card img {
            width: 22px !important;
            height: 22px !important;
            border-radius: 50% !important;
            object-fit: cover !important;
            border: 1px solid #e8e4de !important;
            transition: filter 0.3s ease;
        }
        .bottom-tab-card.grayed img {
            filter: grayscale(100%) !important;
            opacity: 0.6 !important;
        }
        .bottom-tab-card span {
            font-family: 'Cormorant Garamond', Georgia, serif !important;
            font-size: 1.05rem !important;
            font-weight: 500 !important;
            color: #3a3a3a !important;
            -webkit-text-fill-color: #3a3a3a !important;
            letter-spacing: 0.02em !important;
        }
        .bottom-tab-card.grayed span {
            color: #8a857f !important;
            -webkit-text-fill-color: #8a857f !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Sticky persisted header text
    st.markdown(
        f"""
        <div class="sticky-header-container">
            <h1 class="chat-header-text">Cosmic Concierge · {agent_name}</h1>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Horizontal navigation block
    nav_cols = st.columns(4, gap="small")

    # Layout Home, Tarot, Zodiac, Bazi horizontally
    tabs = [
        {"key": "home", "label": "Home", "img": COSMIC_B64},
        {"key": "tarot", "label": "Tarot", "img": TAROT_B64},
        {"key": "zodiac", "label": "Zodiac", "img": ZODIAC_B64},
        {"key": "bazi", "label": "Bazi · 八字", "img": BAZI_B64},
    ]

    for col_idx, tab in enumerate(tabs):
        is_active = (tab["key"] == "home" and st.session_state.active_agent is None) or (tab["key"] == st.session_state.active_agent)
        active_cls = "active" if is_active else "grayed"

        with nav_cols[col_idx]:
            # Native invisible button overlay
            st.button(
                " ",
                key=f"header_nav_{tab['key']}",
                on_click=switch_practice,
                args=(tab["key"],),
                use_container_width=True,
            )

            # Styled visual card
            st.markdown(
                f"""
                <div class="bottom-tab-card {active_cls}">
                    <img src="data:image/png;base64,{tab['img']}" alt="{tab['label']}">
                    <span>{tab['label']}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown('</div>', unsafe_allow_html=True)

    ROLE_META = {
        "assistant": {"avatar": "✦", "css": "assistant"},
        "user":      {"avatar": "⬡", "css": "user"},
    }

    st.markdown('<div class="chat-area">', unsafe_allow_html=True)
    for msg in st.session_state.chat_history:
        meta = ROLE_META[msg["role"]]
        st.markdown(
            f"""
            <div class="msg-row {meta['css']}">
                <div class="msg-avatar {meta['css']}">{meta['avatar']}</div>
                <div class="msg-bubble {meta['css']}">{msg['content']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)

    # Script to scroll to the top of the newest assistant message
    if st.session_state.chat_history and st.session_state.chat_history[-1]["role"] == "assistant":
        st.components.v1.html(
            """
            <script>
            setTimeout(() => {
                const doc = window.parent.document;
                const msgRows = doc.querySelectorAll('.msg-row');
                if (msgRows.length > 0) {
                    const lastRow = msgRows[msgRows.length - 1];
                    lastRow.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
            }, 100);
            </script>
            """,
            height=0,
            width=0,
        )

    # Chat Input Box (floats at the very bottom)
    if user_input := st.chat_input("Ask the cosmos anything …"):
        st.session_state.chat_history.append(
            {"role": "user", "content": user_input}
        )
        with st.spinner("Consulting the cosmos…"):
            reply_html = _run_agent(user_input)
        st.session_state.chat_history.append(
            {"role": "assistant", "content": reply_html}
        )
        st.rerun()