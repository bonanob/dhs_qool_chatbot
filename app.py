import os
import requests
import time
from datetime import datetime, date, time as dt_time
import streamlit as st

from llm import stream_gemini_response, build_system_prompt, get_model
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

def get_webhook_url():
    try:
        return str(st.secrets.get("SHEETS_WEBHOOK_URL", "")).strip()
    except Exception:
        return os.getenv("SHEETS_WEBHOOK_URL", "").strip()

def time_options(start_hour, end_hour, start_minute=0):
    options = []
    hour = start_hour
    minute = start_minute
    while (hour < end_hour) or (hour == end_hour and minute == 0):
        options.append(dt_time(hour, minute))
        minute += 30
        if minute >= 60:
            minute = 0
            hour += 1
    return options

def reset_booking_form():
    st.session_state.full_name = ""
    st.session_state.organization = ""
    st.session_state.address = ""
    st.session_state.email = ""
    st.session_state.occasion = ""
    st.session_state.people_count = 1
    st.session_state.usage_frequency = "One-time"
    st.session_state.cleaning_requested = False
    st.session_state.notes = ""
    st.session_state.date_1 = date.today()
    st.session_state.add_date_2 = False
    st.session_state.add_date_3 = False
    st.session_state.date_2 = date.today()
    st.session_state.date_3 = date.today()
    st.session_state.start_time_1 = time_options(7, 21)[0]
    st.session_state.end_time_1 = time_options(7, 22, start_minute=30)[0]
    st.session_state.start_time_2 = time_options(7, 21)[0]
    st.session_state.end_time_2 = time_options(7, 22, start_minute=30)[0]
    st.session_state.start_time_3 = time_options(7, 21)[0]
    st.session_state.end_time_3 = time_options(7, 22, start_minute=30)[0]

def mark_booking_submit():
    st.session_state.booking_submit_inflight = True
    st.session_state.last_booking_submit = time.time()

def make_submission_id():
    year = datetime.utcnow().year
    if st.session_state.booking_id_year != year:
        st.session_state.booking_id_year = year
        st.session_state.booking_id_counter = 0
    st.session_state.booking_id_counter += 1
    return f"{year}-{st.session_state.booking_id_counter:04d}"










st.set_page_config(page_title=APP_TITLE, layout="wide")

if "messages" not in st.session_state:
    st.session_state.messages = []

if "bookings" not in st.session_state:
    st.session_state.bookings = []
if "pending_prompt" not in st.session_state:
    st.session_state.pending_prompt = ""
if "last_booking_submit" not in st.session_state:
    st.session_state.last_booking_submit = 0.0
if "reset_booking_form_pending" not in st.session_state:
    st.session_state.reset_booking_form_pending = False
if "booking_status" not in st.session_state:
    st.session_state.booking_status = None
if "booking_submit_inflight" not in st.session_state:
    st.session_state.booking_submit_inflight = False
if "booking_id_year" not in st.session_state:
    st.session_state.booking_id_year = datetime.utcnow().year
if "booking_id_counter" not in st.session_state:
    st.session_state.booking_id_counter = 0

st.sidebar.title(APP_TITLE)
mode = st.sidebar.radio("Choose a mode", ["Ask a Question", "Book a Room"], index=0)

st.sidebar.markdown("---")

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
    /* Restore Material icon font so icon text doesn't show */
    section[data-testid="stSidebar"] [data-testid="stIconMaterial"] {
        font-family: "Material Symbols Outlined","Material Symbols Rounded","Material Symbols Sharp",sans-serif;
        font-variation-settings: "FILL" 0, "wght" 400, "GRAD" 0, "opsz" 24;
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
    /* Sidebar collapse button tooltip override */
    button[data-testid="stSidebarCollapseButton"] {
        position: relative;
    }
    button[data-testid="stSidebarCollapseButton"]::after {
        content: "Collapse sidebar";
        position: absolute;
        left: 110%;
        top: 50%;
        transform: translateY(-50%);
        background: #111111;
        color: #ffffff;
        padding: 4px 8px;
        border-radius: 6px;
        font-size: 12px;
        font-family: "Inter", "Helvetica Neue", Helvetica, Arial, sans-serif;
        opacity: 0;
        pointer-events: none;
        white-space: nowrap;
        transition: opacity 0.15s ease;
        z-index: 10;
    }
    button[data-testid="stSidebarCollapseButton"]:hover::after {
        opacity: 1;
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
        gap: 6px;
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
    /* Make booking inputs match date/time height */
    div[data-testid="stTextInput"] input[aria-label="Full name"],
    div[data-testid="stTextInput"] input[aria-label="Email"],
    div[data-testid="stTextInput"] input[aria-label="Occasion"] {
        font-size: 16px;
        padding: 6px 12px;
        height: 38px;
    }
    div[data-testid="stTextInput"] input[aria-label="Organization (optional)"] {
        font-size: 16px;
        padding: 6px 12px;
        height: 38px;
    }
    /* Make booking inputs transparent without affecting chat input */
    div[data-testid="stTextInput"]:has(input[aria-label="Full name"]),
    div[data-testid="stTextInput"]:has(input[aria-label="Email"]),
    div[data-testid="stTextInput"]:has(input[aria-label="Occasion"]) {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
    }
    div[data-testid="stTextInput"]:has(input[aria-label="Organization (optional)"]) {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
    }
    div[data-testid="stTextInput"] input[aria-label="Full name"],
    div[data-testid="stTextInput"] input[aria-label="Email"],
    div[data-testid="stTextInput"] input[aria-label="Occasion"] {
        background: transparent !important;
    }
    div[data-testid="stTextInput"] input[aria-label="Organization (optional)"] {
        background: transparent !important;
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
    /* Normalize text inputs inside forms (booking fields) */
    div[data-testid="stForm"] div[data-testid="stTextInput"] {
        box-shadow: none;
        border-radius: 12px;
        background: transparent !important;
        border: none !important;
    }
    div[data-testid="stForm"] div[data-testid="stTextInput"] input {
        font-size: 16px;
        padding: 6px 12px;
        height: 38px;
    }
    /* Make form labels transparent to match background */
    div[data-testid="stForm"] label[data-testid="stWidgetLabel"] {
        background: transparent !important;
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
    /* Booking form styling */
    .booking-form label[data-testid="stWidgetLabel"] {
        font-family: "Inter", "Helvetica Neue", Helvetica, Arial, sans-serif;
        font-size: 14px;
        font-weight: 500;
    }
    .booking-form div[data-testid="stCheckbox"] {
        margin-top: 21px;
        display: flex;
        align-items: center;
        gap: 6px;
    }
    .booking-form div[data-testid="stCheckbox"] label {
        font-family: "Inter", "Helvetica Neue", Helvetica, Arial, sans-serif;
        font-size: 14px;
        font-weight: 500;
        margin-top: 0;
    }
    /* Force light booking form controls on Cloud */
    .booking-form input,
    .booking-form textarea,
    .booking-form select {
        background: #ffffff !important;
        color: #111111 !important;
    }
    .booking-form div[data-baseweb="input"] > div,
    .booking-form div[data-baseweb="textarea"] > div,
    .booking-form div[data-baseweb="select"] > div,
    .booking-form div[data-baseweb="select"] {
        background: #ffffff !important;
        border: 1px solid #E6E6E2 !important;
        box-shadow: none !important;
    }
    .booking-form div[data-baseweb="select"] span,
    .booking-form div[data-baseweb="select"] input {
        color: #111111 !important;
    }
    .booking-form div[data-baseweb="select"] svg {
        fill: #111111 !important;
    }
    .booking-form button[data-testid="stBaseButton-secondary"] {
        background: #111111 !important;
        color: #ffffff !important;
        border: 1px solid #111111 !important;
    
</style>
""",
    unsafe_allow_html=True,
)

# Remove the default tooltip/title from the sidebar collapse control (if present).
st.components.v1.html(
    """
    <script>
    (function() {
      const root = window.parent.document;
      const clearTitles = (scope) => {
        const elts = scope.querySelectorAll('[title]');
        elts.forEach((el) => {
          // Preserve meaningful tooltips outside the sidebar
          if (el.closest('section[data-testid="stSidebar"]')) {
            el.setAttribute('title', '');
          }
        });
      };

      const sidebar = root.querySelector('section[data-testid="stSidebar"]');
      if (sidebar) {
        clearTitles(sidebar);
        // Clear any new title attributes added later.
        const observer = new MutationObserver((mutations) => {
          mutations.forEach((m) => {
            if (m.type === 'attributes' && m.attributeName === 'title') {
              if (m.target && m.target.closest('section[data-testid="stSidebar"]')) {
                m.target.setAttribute('title', '');
              }
            }
            if (m.addedNodes && m.addedNodes.length) {
              m.addedNodes.forEach((node) => {
                if (node.querySelectorAll) {
                  clearTitles(node);
                }
              });
            }
          });
        });
        observer.observe(sidebar, { attributes: true, childList: true, subtree: true });
      }
    })();
    </script>
    """,
    height=0,
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

if "faq_text" not in st.session_state:
    st.session_state.faq_text = ""
    st.session_state.faq_source = ""
    st.session_state.faq_warned = False
    local_text = load_local_faq(FAQ_PDF_PATH)
    if local_text:
        st.session_state.faq_text = local_text
        st.session_state.faq_source = "local"
        if len(st.session_state.faq_text) > MAX_FAQ_CHARS:
            st.session_state.faq_text = st.session_state.faq_text[:MAX_FAQ_CHARS]
            st.session_state.faq_warned = True

if st.session_state.faq_warned:
    st.sidebar.warning("FAQ content is long; truncated for prompt size.")

if "system_prompt" not in st.session_state:
    st.session_state.system_prompt = build_system_prompt(st.session_state.faq_text)

model_name = get_model_name()

# Warm the model once per session to reduce first-token latency.
if "model_warmed" not in st.session_state:
    st.session_state.model_warmed = True
    _ = get_model(model_name, st.session_state.system_prompt)

if mode == "Ask a Question":
    st.markdown('<div class="codex-subtitle">Qool Frontdesk</div>', unsafe_allow_html=True)
    st.markdown('<div class="codex-title">What can I help with?</div>', unsafe_allow_html=True)
    thinking_placeholder = st.empty()

    def queue_submit():
        st.session_state.pending_prompt = st.session_state.query_input.strip()
        st.session_state.query_input = ""

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

    chat_container = st.container()

    if st.session_state.messages:
        with chat_container:
            st.markdown('<div class="chat-stack">', unsafe_allow_html=True)
            for msg in st.session_state.messages:
                role = msg["role"]
                css_role = "user" if role == "user" else "assistant"
                st.markdown(
                    f'<div class="bubble {css_role}">{msg["content"]}</div>',
                    unsafe_allow_html=True,
                )
            st.markdown("</div>", unsafe_allow_html=True)

    if st.session_state.pending_prompt:
        user_text = st.session_state.pending_prompt
        st.session_state.pending_prompt = ""
        st.session_state.messages.append({"role": "user", "content": user_text})

        with chat_container:
            st.markdown('<div class="chat-stack">', unsafe_allow_html=True)
            st.markdown(
                f'<div class="bubble user">{user_text}</div>',
                unsafe_allow_html=True,
            )
            assistant_text = ""
            streaming_placeholder = st.empty()
            if len(st.session_state.messages) > 1:
                time.sleep(1)
            for chunk in stream_gemini_response(
                messages=st.session_state.messages[-MAX_HISTORY_MESSAGES:],
                system_prompt=st.session_state.system_prompt,
                model_name=model_name,
            ):
                assistant_text += chunk
                streaming_placeholder.markdown(
                    f'<div class="bubble assistant">{assistant_text}</div>',
                    unsafe_allow_html=True,
                )
            if not assistant_text.strip():
                assistant_text = "I couldn't generate a response. Please try again."
                streaming_placeholder.markdown(
                    f'<div class="bubble assistant">{assistant_text}</div>',
                    unsafe_allow_html=True,
                )
            st.markdown("</div>", unsafe_allow_html=True)

        st.session_state.messages.append({"role": "assistant", "content": assistant_text})

    # Intentionally no footer banner to keep the UI minimal.

elif mode == "Book a Room":
    st.subheader("Booking Form")

    if st.session_state.reset_booking_form_pending:
        reset_booking_form()
        st.session_state.reset_booking_form_pending = False

    st.markdown('<div class="booking-form">', unsafe_allow_html=True)
    with st.container():
        col1, col2 = st.columns(2)
        with col1:
            full_name = st.text_input("Full name", key="full_name")
        with col2:
            organization = st.text_input("Organization (optional)", key="organization")

        address = st.text_area("Address", key="address", height=80)

        col3, col4 = st.columns(2)
        with col3:
            email = st.text_input("Email", key="email")
        with col4:
            occasion = st.text_input("Occasion", key="occasion")

        col5, col6, col7 = st.columns(3)
        with col5:
            people_count = st.number_input("Number of people", min_value=1, step=1, key="people_count")
        with col6:
            usage_frequency = st.selectbox("Usage frequency", ["One-time", "Weekly", "Monthly"], key="usage_frequency")
        with col7:
            cleaning_requested = st.checkbox("Cleaning requested (20 Euros)", value=False, key="cleaning_requested")

        booking_date = st.date_input("Date", min_value=date.today(), key="date_1")

        col8, col9, col10 = st.columns([1, 1, 1])
        with col8:
            start_time = st.selectbox("Start time", time_options(7, 21), key="start_time_1", format_func=lambda t: t.strftime("%H:%M"))
        with col9:
            end_time = st.selectbox("End time", time_options(7, 22, start_minute=30), key="end_time_1", format_func=lambda t: t.strftime("%H:%M"))
        with col10:
            add_date_2 = st.checkbox("Add date", value=False, key="add_date_2")

        booking_date_2 = None
        start_time_2 = None
        end_time_2 = None
        add_date_3 = False
        if add_date_2:
            booking_date_2 = st.date_input("Backup date 1", min_value=date.today(), key="date_2")

            col11, col12, col13 = st.columns([1, 1, 1])
            with col11:
                start_time_2 = st.selectbox("Start time", time_options(7, 21), key="start_time_2", format_func=lambda t: t.strftime("%H:%M"))
            with col12:
                end_time_2 = st.selectbox("End time", time_options(7, 22, start_minute=30), key="end_time_2", format_func=lambda t: t.strftime("%H:%M"))
            with col13:
                add_date_3 = st.checkbox("Add another date", value=False, key="add_date_3")

        booking_date_3 = None
        start_time_3 = None
        end_time_3 = None
        if add_date_3:
            booking_date_3 = st.date_input("Backup date 2", min_value=date.today(), key="date_3")

            col14, col15, _ = st.columns([1, 1, 1])
            with col14:
                start_time_3 = st.selectbox("Start time", time_options(7, 21), key="start_time_3", format_func=lambda t: t.strftime("%H:%M"))
            with col15:
                end_time_3 = st.selectbox("End time", time_options(7, 22, start_minute=30), key="end_time_3", format_func=lambda t: t.strftime("%H:%M"))

        notes = st.text_area("Notes (optional)", key="notes")
        status_placeholder = st.empty()
        if st.session_state.booking_status:
            level, msg = st.session_state.booking_status
            if level == "success":
                status_placeholder.success(msg)
            elif level == "error":
                status_placeholder.error(msg)
            elif level == "warning":
                status_placeholder.warning(msg)

        cooldown = (time.time() - st.session_state.last_booking_submit) < 5
        missing_required = (
            not full_name.strip()
            or not email.strip()
            or "@" not in email
            or not address.strip()
            or people_count < 1
        )
        submitted = st.button(
            "Submit booking request",
            disabled=cooldown or missing_required or st.session_state.booking_submit_inflight,
            on_click=mark_booking_submit,
        )
    st.markdown("</div>", unsafe_allow_html=True)

    if submitted:
        st.session_state.booking_status = None
        errors = []
        if not full_name.strip():
            errors.append("Name is required.")
        if not email.strip() or "@" not in email:
            errors.append("Valid email is required.")
        if not address.strip():
            errors.append("Address is required.")
        if people_count < 1:
            errors.append("Number of people must be at least 1.")
        def minutes_between(t_start, t_end):
            return (t_end.hour * 60 + t_end.minute) - (t_start.hour * 60 + t_start.minute)

        def in_range(t):
            return dt_time(7, 0) <= t <= dt_time(22, 0)

        if not in_range(start_time) or not in_range(end_time):
            errors.append("Booking times must be between 7:00 and 22:00.")
        if start_time >= end_time or minutes_between(start_time, end_time) < 30:
            errors.append("Booking must be at least 30 minutes, with end time after start time.")
        if booking_date_2 and start_time_2 and end_time_2:
            if not in_range(start_time_2) or not in_range(end_time_2):
                errors.append("Backup date 1 times must be between 7:00 and 22:00.")
            if start_time_2 >= end_time_2 or minutes_between(start_time_2, end_time_2) < 30:
                errors.append("Backup date 1 must be at least 30 minutes, with end time after start time.")
        if booking_date_3 and start_time_3 and end_time_3:
            if not in_range(start_time_3) or not in_range(end_time_3):
                errors.append("Backup date 2 times must be between 7:00 and 22:00.")
            if start_time_3 >= end_time_3 or minutes_between(start_time_3, end_time_3) < 30:
                errors.append("Backup date 2 must be at least 30 minutes, with end time after start time.")

        if errors:
            st.session_state.booking_submit_inflight = False
            for err in errors:
                st.error(err)
        else:
            booking = {
                "name": full_name.strip(),
                "organization": organization.strip(),
                "address": address.strip(),
                "email": email.strip(),
                "occasion": occasion.strip(),
                "people_count": int(people_count),
                "usage_frequency": usage_frequency,
                "cleaning_requested": bool(cleaning_requested),
                "cleaning_fee": 20 if cleaning_requested else 0,
                "date": booking_date.isoformat(),
                "start": start_time.strftime("%H:%M"),
                "end": end_time.strftime("%H:%M"),
                "backup_1": {
                    "date": booking_date_2.isoformat() if booking_date_2 else "",
                    "start": start_time_2.strftime("%H:%M") if start_time_2 else "",
                    "end": end_time_2.strftime("%H:%M") if end_time_2 else "",
                },
                "backup_2": {
                    "date": booking_date_3.isoformat() if booking_date_3 else "",
                    "start": start_time_3.strftime("%H:%M") if start_time_3 else "",
                    "end": end_time_3.strftime("%H:%M") if end_time_3 else "",
                },
                "notes": notes.strip(),
                "submitted_at": datetime.utcnow().isoformat() + "Z",
                "submission_id": make_submission_id(),
            }
            webhook_url = get_webhook_url()
            if webhook_url:
                try:
                    resp = requests.post(webhook_url, json=booking, timeout=10)
                    if resp.status_code >= 400:
                        detail = resp.text.strip()
                        if detail:
                            st.session_state.booking_status = (
                                "error",
                                f"Failed to write to Google Sheets (HTTP {resp.status_code}): {detail}",
                            )
                        else:
                            st.session_state.booking_status = (
                                "error",
                                f"Failed to write to Google Sheets (HTTP {resp.status_code}).",
                            )
                        st.session_state.booking_submit_inflight = False
                    else:
                        st.session_state.bookings.append(booking)
                        st.session_state.booking_status = ("success", "Booking request submitted.")
                        st.session_state.booking_submit_inflight = False
                        st.session_state.reset_booking_form_pending = True
                        st.rerun()
                except Exception as exc:
                    st.session_state.booking_status = ("error", f"Failed to write to Google Sheets: {exc}")
                    st.session_state.booking_submit_inflight = False
            else:
                st.session_state.bookings.append(booking)
                st.session_state.booking_status = ("warning", "SHEETS_WEBHOOK_URL is not set; booking saved only for this session.")
                st.session_state.booking_submit_inflight = False
                st.session_state.reset_booking_form_pending = True
                st.rerun()

    # Remove debug booking JSON output from the UI.
