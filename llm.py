import os
import streamlit as st
try:
    import tomllib  # py3.11+
except Exception:  # pragma: no cover
    tomllib = None

DEFAULT_SYSTEM_PROMPT = """You are the helpful community manager for the building.\n\nRules:\n- Answer ONLY using the provided FAQ/policy text.\n- If the answer is not in the FAQ/policy text, say you don't know and ask the user to check with management.\n- Do not guess or add rules that are not stated.\n"""


def load_base_prompt():
    base_path = os.path.join(os.path.dirname(__file__), "prompts", "system_prompt.txt")
    if os.path.exists(base_path):
        with open(base_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    return DEFAULT_SYSTEM_PROMPT.strip()


def build_system_prompt(faq_text: str) -> str:
    base = load_base_prompt()
    faq_block = faq_text.strip()
    if not faq_block:
        return base + "\n\nFAQ: (not provided)"
    return base + "\n\nFAQ:\n" + faq_block


def _to_gemini_messages(messages):
    gemini_messages = []
    for msg in messages:
        role = msg.get("role")
        content = msg.get("content", "")
        if role == "assistant":
            gemini_role = "model"
        else:
            gemini_role = "user"
        gemini_messages.append({"role": gemini_role, "parts": [content]})
    return gemini_messages


@st.cache_resource
def get_model(model_name: str, system_prompt: str):
    import google.generativeai as genai

    genai.configure(api_key=_get_api_key())
    return genai.GenerativeModel(
        model_name=model_name,
        system_instruction=system_prompt,
    )


def _get_api_key() -> str:
    api_key = ""
    try:
        api_key = str(st.secrets.get("GEMINI_API_KEY", "")).strip()
    except Exception:
        api_key = ""
    if not api_key:
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        secrets_path = os.path.join(os.getcwd(), ".streamlit", "secrets.toml")
        if tomllib and os.path.exists(secrets_path):
            try:
                with open(secrets_path, "rb") as f:
                    data = tomllib.load(f)
                api_key = str(data.get("GEMINI_API_KEY", "")).strip()
            except Exception:
                api_key = ""
    if not api_key:
        return ""
    return api_key


def stream_gemini_response(messages, system_prompt, model_name="gemini-2.5-flash-lite"):
    api_key = _get_api_key()
    if not api_key:
        yield "GEMINI_API_KEY is missing. Set it in your environment or Streamlit secrets."
        return

    try:
        model = get_model(model_name, system_prompt)
        history = _to_gemini_messages(messages)
        stream = model.generate_content(history, stream=True)
        for chunk in stream:
            text = getattr(chunk, "text", "")
            if text:
                yield text
    except Exception as exc:
        msg = str(exc)
        if "ResourceExhausted" in msg or "429" in msg:
            yield "You’ve hit the free-tier rate limit. Please wait a bit and try again."
        else:
            yield "Sorry, something went wrong while generating the response. Please try again."
