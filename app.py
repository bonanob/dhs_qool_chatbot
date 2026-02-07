import os
from datetime import datetime, date
import streamlit as st

from llm import stream_gemini_response, build_system_prompt
from pdf_utils import extract_pdf_text

APP_TITLE = "Community Room Assistant"
DEFAULT_MODEL_NAME = "gemini-2.5-flash-lite"
MAX_FAQ_CHARS = 30000
MAX_HISTORY_MESSAGES = 12
FAQ_PDF_PATH = os.path.join(os.path.dirname(__file__), "prompts", "faq.pdf")


def get_model_name():
    try:
        return str(st.secrets.get("MODEL_NAME", DEFAULT_MODEL_NAME)).strip() or DEFAULT_MODEL_NAME
    except Exception:
        return os.getenv("MODEL_NAME", DEFAULT_MODEL_NAME).strip() or DEFAULT_MODEL_NAME

st.set_page_config(page_title=APP_TITLE, layout="wide")

if "messages" not in st.session_state:
    st.session_state.messages = []

if "bookings" not in st.session_state:
    st.session_state.bookings = []
if "pending_prompt" not in st.session_state:
    st.session_state.pending_prompt = ""

st.sidebar.title(APP_TITLE)
mode = st.sidebar.radio("Choose a mode", ["Ask a Question", "Book a Room"], index=0)

st.sidebar.markdown("---")
st.sidebar.caption("Tip: Place a PDF at prompts/faq.pdf to ground answers.")

st.markdown(
    """
<style>
    :root {
        --bg: #F3F3F2;
        --ink: #111111;
        --muted: #6B6B6B;
        --pill: #EFEFED;
        --panel: #ECECEA;
        --hairline: #E1E1DE;
        --shadow: 0 18px 60px rgba(0, 0, 0, 0.08);
        --sidebar-w: 18rem;
    }
    .stApp {
        background: var(--bg);
    }
    header, footer { visibility: hidden; }
    .block-container {
        max-width: 980px;
        padding-top: 6.5rem;
        padding-bottom: 8rem;
    }
    /* Sidebar harmonization */
    section[data-testid="stSidebar"] {
        background: var(--panel);
        border-right: 1px solid var(--hairline);
        width: var(--sidebar-w);
    }
    section[data-testid="stSidebar"] * {
        font-family: "Inter", "Helvetica Neue", Helvetica, Arial, sans-serif;
        color: var(--ink);
    }
    section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] label {
        background: #F6F6F4;
        border-radius: 999px;
        padding: 6px 12px;
        border: 1px solid var(--hairline);
        margin-bottom: 6px;
    }
    section[data-testid="stSidebar"] hr {
        border-color: var(--hairline);
    }
    .codex-title {
        font-family: "Inter", "Helvetica Neue", Helvetica, Arial, sans-serif;
        font-size: 40px;
        font-weight: 700;
        color: var(--ink);
        text-align: center;
        letter-spacing: -0.5px;
        margin-bottom: 1.5rem;
    }
    .codex-subtitle {
        text-align: center;
        font-family: "Inter", "Helvetica Neue", Helvetica, Arial, sans-serif;
        color: var(--muted);
        font-weight: 600;
        letter-spacing: 0.2px;
        margin-bottom: 0.5rem;
    }
    .input-shell {
        background: transparent;
        border-radius: 28px;
        box-shadow: none;
        padding: 0;
        border: none;
        margin: 0 auto;
    }
    .input-shell-bottom {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 10px 6px 4px 6px;
    }
    .chip-row {
        display: inline-flex;
        gap: 8px;
        align-items: center;
    }
    .chip {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 6px 10px;
        border-radius: 999px;
        border: 1px solid #E1E1DE;
        background: #F7F7F5;
        color: #4E4E4E;
        font-family: "Inter", "Helvetica Neue", Helvetica, Arial, sans-serif;
        font-size: 12px;
        font-weight: 600;
    }
    .chip-dot {
        width: 10px;
        height: 10px;
        border-radius: 50%;
        border: 1px solid #8E8E8E;
        display: inline-block;
    }
    .chip-icon {
        width: 12px;
        height: 12px;
        border: 1px solid #8E8E8E;
        border-radius: 3px;
        display: inline-block;
    }
    .send-btn {
        width: 40px;
        height: 40px;
        border-radius: 12px;
        background: #111111;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        color: #ffffff;
        font-weight: 700;
        font-size: 16px;
        border: none;
    }
    .pill {
        display: inline-flex;
        align-items: center;
        padding: 6px 12px;
        border-radius: 999px;
        background: var(--pill);
        color: var(--ink);
        font-family: "Inter", "Helvetica Neue", Helvetica, Arial, sans-serif;
        font-weight: 600;
        font-size: 12px;
        border: 1px solid var(--hairline);
        gap: 6px;
    }
    .pill-icon {
        width: 10px;
        height: 10px;
        border: 1px solid var(--ink);
        border-radius: 2px;
        display: inline-block;
    }
    div[data-testid="stTextInput"] {
        background: #ffffff !important;
        border-radius: 18px;
        padding: 0;
        margin: 0;
        border: 1px solid #E6E6E2;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.08);
    }
    div[data-testid="stTextInput"] > div {
        padding: 0;
        border: none;
        background: #ffffff !important;
    }
    div[data-testid="stTextInput"] input {
        border: none;
        background: #ffffff !important;
        font-family: "Inter", "Helvetica Neue", Helvetica, Arial, sans-serif;
        font-size: 18px;
        color: #111111;
        padding: 14px 16px;
    }
    div[data-testid="stTextInput"] input::placeholder {
        color: #9A9A98;
    }
    div[data-testid="stTextInput"] input:focus {
        outline: none !important;
        box-shadow: none !important;
    }
    div[data-testid="stTextInput"] input:focus {
        box-shadow: none;
    }
    button[kind="primary"] {
        display: none !important;
    }
    div[data-testid="stFormSubmitButton"] {
        display: none !important;
    }
    /* Spinner harmony */
    .stSpinner > div {
        border-top-color: var(--ink) !important;
        border-right-color: var(--hairline) !important;
        border-bottom-color: var(--hairline) !important;
        border-left-color: var(--hairline) !important;
    }
    .stSpinner {
        color: var(--muted) !important;
    }
    .thinking {
        text-align: center;
        font-family: "Inter", "Helvetica Neue", Helvetica, Arial, sans-serif;
        color: var(--muted);
        font-size: 14px;
        margin-top: 6px;
        margin-bottom: 18px;
    }
    /* Hide Streamlit "Running ..." tool status to keep UI clean */
    div[data-testid="stStatus"] {
        display: none !important;
    }
    .codex-banner {
        margin-top: 2.5rem;
        display: inline-flex;
        padding: 6px 14px;
        border-radius: 999px;
        background: #ECECEA;
        color: #7A7A7A;
        font-family: "Inter", "Helvetica Neue", Helvetica, Arial, sans-serif;
        font-size: 12px;
    }
    .center-wrap {
        display: flex;
        justify-content: center;
    }
    .chat-label {
        color: #5A5A58;
        font-weight: 600;
        letter-spacing: 0.2px;
    }
    .chat-body {
        color: #1F1F1F;
    }
    .chat-stack {
        display: flex;
        flex-direction: column;
        gap: 20px;
        margin-top: 2rem;
    }
    .bubble {
        max-width: 70%;
        padding: 12px 16px;
        border-radius: 18px;
        font-family: "Inter", "Helvetica Neue", Helvetica, Arial, sans-serif;
        font-size: 15px;
        line-height: 1.4;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.06);
        margin-top: 6px;
        margin-bottom: 6px;
    }
    .bubble.user {
        margin-left: auto;
        background: #111111;
        color: #ffffff;
        border-bottom-right-radius: 6px;
    }
    .bubble.assistant {
        margin-right: auto;
        background: #ffffff;
        color: #1F1F1F;
        border: 1px solid #E6E6E2;
        border-bottom-left-radius: 6px;
    }
</style>
""",
    unsafe_allow_html=True,
)

@st.cache_data(show_spinner=False)
def extract_pdf_cached(pdf_bytes: bytes) -> str:
    return extract_pdf_text(pdf_bytes)


@st.cache_data(show_spinner=False)
def load_local_faq(file_path: str) -> str:
    if os.path.exists(file_path):
        with open(file_path, "rb") as f:
            return extract_pdf_cached(f.read())
    return ""

faq_text = ""
faq_source = ""
local_text = load_local_faq(FAQ_PDF_PATH)
if local_text:
    faq_text = local_text
    faq_source = "local"
    if len(faq_text) > MAX_FAQ_CHARS:
        faq_text = faq_text[:MAX_FAQ_CHARS]
        st.sidebar.warning("FAQ content is long; truncated for prompt size.")

system_prompt = build_system_prompt(faq_text)
model_name = get_model_name()

if mode == "Ask a Question":
    st.markdown('<div class="codex-subtitle">Codex</div>', unsafe_allow_html=True)
    st.markdown('<div class="codex-title">What can I help with?</div>', unsafe_allow_html=True)
    thinking_placeholder = st.empty()

    def queue_submit():
        st.session_state.pending_prompt = st.session_state.query_input.strip()

    if st.session_state.messages:
        st.markdown(
            """
            <style>
            div[data-testid="stTextInput"]{
                position: fixed;
                left: calc(50% + (var(--sidebar-w) / 2));
                transform: translateX(-50%);
                bottom: 28px;
                width: min(720px, calc(100% - 4rem));
                z-index: 50;
            }
            @media (max-width: 900px) {
                div[data-testid="stTextInput"]{
                    left: 50%;
                }
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """
            <style>
            div[data-testid="stTextInput"]{
                position: static;
                width: 100%;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )

    st.text_input(
        "Ask",
        key="query_input",
        placeholder="Ask anything",
        label_visibility="collapsed",
        on_change=queue_submit,
    )

    if st.session_state.pending_prompt:
        user_text = st.session_state.pending_prompt
        st.session_state.pending_prompt = ""
        thinking_placeholder.markdown('<div class="thinking">Thinking...</div>', unsafe_allow_html=True)
        st.session_state.messages.append({"role": "user", "content": user_text})
        assistant_text = ""
        for chunk in stream_gemini_response(
            messages=st.session_state.messages[-MAX_HISTORY_MESSAGES:],
            system_prompt=system_prompt,
            model_name=model_name,
        ):
            assistant_text += chunk
        if not assistant_text.strip():
            assistant_text = "I couldn't generate a response. Please try again."
        st.session_state.messages.append({"role": "assistant", "content": assistant_text})
        thinking_placeholder.empty()
        st.rerun()

    if st.session_state.messages:
        st.markdown('<div class="chat-stack">', unsafe_allow_html=True)
        for msg in st.session_state.messages:
            role = msg["role"]
            css_role = "user" if role == "user" else "assistant"
            st.markdown(
                f'<div class="bubble {css_role}">{msg["content"]}</div>',
                unsafe_allow_html=True,
            )
        st.markdown("</div>", unsafe_allow_html=True)

    # Intentionally no footer banner to keep the UI minimal.

elif mode == "Book a Room":
    st.subheader("Booking Form")

    with st.form("booking_form"):
        col1, col2 = st.columns(2)
        with col1:
            full_name = st.text_input("Full name")
            email = st.text_input("Email")
            room = st.selectbox("Room", ["Lounge", "Kitchen", "Study Room"])
        with col2:
            booking_date = st.date_input("Date", min_value=date.today())
            start_time = st.time_input("Start time")
            end_time = st.time_input("End time")

        notes = st.text_area("Notes (optional)")
        submitted = st.form_submit_button("Submit booking request")

    if submitted:
        errors = []
        if not full_name.strip():
            errors.append("Name is required.")
        if not email.strip() or "@" not in email:
            errors.append("Valid email is required.")
        if start_time >= end_time:
            errors.append("End time must be after start time.")

        if errors:
            for err in errors:
                st.error(err)
        else:
            booking = {
                "name": full_name.strip(),
                "email": email.strip(),
                "room": room,
                "date": booking_date.isoformat(),
                "start": start_time.strftime("%H:%M"),
                "end": end_time.strftime("%H:%M"),
                "notes": notes.strip(),
                "submitted_at": datetime.utcnow().isoformat() + "Z",
            }
            st.session_state.bookings.append(booking)
            st.success("Booking request submitted. You can connect this to a database later.")

    if st.session_state.bookings:
        st.markdown("---")
        st.caption("Recent booking requests (session only)")
        st.json(st.session_state.bookings)
