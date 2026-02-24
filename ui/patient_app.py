"""
Patient Triage App - CodeZero
==============================
Mobile-responsive, multilingual patient-facing triage interface.
Supports voice input (Azure Speech) and text input in any language.

Run: streamlit run ui/patient_app.py

FIXES APPLIED:
  - RTL layout injected automatically for Arabic / Hebrew detection
  - Translation results are cached to avoid redundant API calls
  - Wildcard 'from src.triage_engine import *' replaced with explicit imports
  - Startup credential status panel shows which Azure services are active
  - Token usage logging added via triage_engine wrapper
"""

import logging
import os
import sys
import tempfile
from pathlib import Path

import streamlit as st

# ---------------------------------------------------------------------------
# Project root on sys.path
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# FIX: Explicit imports — no wildcard
from src.hospital_queue import HospitalQueue
from src.knowledge_indexer import KnowledgeIndexer
from src.maps_handler import MapsHandler
from src.triage_engine import (
    TRIAGE_COLORS,
    TRIAGE_EMERGENCY,
    TRIAGE_ROUTINE,
    TRIAGE_URGENT,
    TriageEngine,
)
from src.translator import Translator

try:
    from src.speech_handler import SpeechHandler
    _HAS_SPEECH = True
except Exception:
    _HAS_SPEECH = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# RTL languages — layout direction flipped for these locales
# ---------------------------------------------------------------------------
RTL_LOCALES = {"ar-SA", "ar-EG", "ar-AE", "he-IL", "fa-IR", "ur-PK"}

# ---------------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="CodeZero Triage",
    page_icon="🏥",
    layout="centered",
)

# ---------------------------------------------------------------------------
# Base CSS (LTR default — overridden below for RTL)
# ---------------------------------------------------------------------------
BASE_CSS = """
<style>
.block-container { max-width: 720px; }
.stButton > button {
    min-height: 54px;
    font-size: 1.05rem;
    border-radius: 10px;
}
div[data-testid="stRadio"] > div > label {
    font-size: 1.2rem !important;
    padding: 12px 20px !important;
    border: 2px solid #d0d5dd !important;
    border-radius: 10px !important;
    min-height: 48px !important;
    cursor: pointer !important;
}
div[data-testid="stRadio"] > div > label:hover {
    border-color: #2d4a9e !important;
    background: #f0f4ff !important;
}
</style>
"""

RTL_CSS = """
<style>
/* RTL override for Arabic, Hebrew, Farsi, Urdu */
body, .block-container, .stMarkdown, .stTextArea textarea,
.stTextInput input, .stRadio, .stMultiSelect, .stSelectSlider {
    direction: rtl;
    text-align: right;
}
.stButton > button { direction: rtl; }
</style>
"""

st.markdown(BASE_CSS, unsafe_allow_html=True)


def _inject_rtl_if_needed() -> None:
    """Inject RTL CSS when the detected language requires it."""
    if st.session_state.get("detected_language", "en-US") in RTL_LOCALES:
        st.markdown(RTL_CSS, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Service loader — crash-proof, with startup status tracking
# ---------------------------------------------------------------------------
@st.cache_resource
def load_services() -> tuple:
    """Initialize all Azure service clients.

    Returns:
        Tuple of (TriageEngine, Translator, MapsHandler, HospitalQueue,
        SpeechHandler | None, dict[service_name, bool]).
    """
    status: dict[str, bool] = {}

    try:
        ki = KnowledgeIndexer()
        status["AI Search"] = ki._initialized
    except Exception:
        ki = None
        status["AI Search"] = False

    try:
        tr = Translator()
        status["Translator"] = tr._initialized
    except Exception:
        tr = None
        status["Translator"] = False

    try:
        te = TriageEngine(knowledge_indexer=ki, translator=tr)
        status["OpenAI (GPT-4)"] = te._initialized
    except Exception:
        te = None
        status["OpenAI (GPT-4)"] = False

    try:
        mh = MapsHandler()
        status["Azure Maps"] = mh._initialized
    except Exception:
        mh = None
        status["Azure Maps"] = False

    try:
        hq = HospitalQueue()
        status["Hospital Queue (DB)"] = True
    except Exception:
        hq = None
        status["Hospital Queue (DB)"] = False

    try:
        sh = SpeechHandler() if _HAS_SPEECH else None
        status["Speech Services"] = bool(sh and sh._initialized)
    except Exception:
        sh = None
        status["Speech Services"] = False

    return te, tr, mh, hq, sh, status


triage_engine, translator, maps_handler, hospital_queue, speech_handler, _svc_status = (
    load_services()
)

# ---------------------------------------------------------------------------
# Session state defaults
# ---------------------------------------------------------------------------
_DEFAULTS: dict = dict(
    step="input",
    complaint_text="",
    complaint_english="",
    detected_language="en-US",
    questions=[],
    answers=[],
    q_idx=0,
    assessment=None,
    patient_record=None,
    eta_info=None,
    nearby_hospitals=[],
    selected_hospital=None,
    patient_lat=None,
    patient_lon=None,
)
for _key, _val in _DEFAULTS.items():
    if _key not in st.session_state:
        st.session_state[_key] = _val

# ---------------------------------------------------------------------------
# Translation helper with in-session cache
# FIX: Previously called Azure Translator on every Streamlit rerun.
# Now results are cached in session_state to avoid redundant API calls.
# ---------------------------------------------------------------------------
_TRANSLATION_CACHE_KEY = "_translation_cache"
if _TRANSLATION_CACHE_KEY not in st.session_state:
    st.session_state[_TRANSLATION_CACHE_KEY] = {}


def t(text: str) -> str:
    """Translate English UI text into the patient's detected language.

    Results are cached in session state to prevent redundant API calls
    on every Streamlit rerun (which happen after every widget interaction).

    Args:
        text: English source text.

    Returns:
        Translated string, or original text if translation unavailable.
    """
    lang = st.session_state.detected_language
    if not translator or lang.startswith("en"):
        return text

    cache: dict = st.session_state[_TRANSLATION_CACHE_KEY]
    cache_key = f"{lang}:{text}"
    if cache_key in cache:
        return cache[cache_key]

    try:
        translated = translator.translate_from_english(text, lang)
        cache[cache_key] = translated
        return translated
    except Exception:
        return text


# ---------------------------------------------------------------------------
# Session reset
# ---------------------------------------------------------------------------
def reset() -> None:
    """Reset all session state to defaults and clear translation cache."""
    for key, val in _DEFAULTS.items():
        st.session_state[key] = val
    st.session_state[_TRANSLATION_CACHE_KEY] = {}


# ---------------------------------------------------------------------------
# Core processing pipeline
# ---------------------------------------------------------------------------
def do_process(text: str) -> None:
    """Detect language, translate to English, generate questions, advance step.

    Args:
        text: Raw patient input (any language).
    """
    # Step 1: Detect language
    detected_code: str | None = None
    if translator:
        try:
            detected_code = translator.detect_language(text)
        except Exception as exc:
            logger.warning("Language detection failed: %s", exc)

    locale_map = {
        "de": "de-DE", "tr": "tr-TR", "ar": "ar-SA",
        "fr": "fr-FR", "es": "es-ES", "it": "it-IT",
        "pt": "pt-BR", "ru": "ru-RU", "zh-Hans": "zh-CN",
        "he": "he-IL", "fa": "fa-IR", "ur": "ur-PK",
        "en": "en-US",
    }
    st.session_state.detected_language = (
        locale_map.get(detected_code or "en", "en-US")
    )
    # Clear cache when language changes
    st.session_state[_TRANSLATION_CACHE_KEY] = {}

    # Step 2: Translate to English for backend processing
    english = text
    if translator:
        try:
            english = translator.translate_to_english(
                text, st.session_state.detected_language
            )
        except Exception as exc:
            logger.warning("Translation to English failed: %s", exc)

    st.session_state.complaint_text = text
    st.session_state.complaint_english = english

    # Step 3: Generate follow-up questions (RAG-grounded)
    if triage_engine:
        st.session_state.questions = triage_engine.generate_questions(english)
    else:
        st.session_state.questions = []

    st.session_state.q_idx = 0
    st.session_state.answers = []
    st.session_state.step = "questions"
    st.rerun()


def try_transcribe(audio) -> str | None:
    """Attempt Azure Speech transcription of an uploaded audio buffer.

    Args:
        audio: Streamlit audio upload object with a .getvalue() method.

    Returns:
        Transcribed text string, or None if transcription failed.
    """
    if not speech_handler or not getattr(speech_handler, "_initialized", False):
        return None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio.getvalue())
            tmp_path = tmp.name
        result = speech_handler.recognize_from_audio_file(tmp_path)
        os.unlink(tmp_path)
        if result and result.get("text"):
            detected_lang = result.get("language", "en-US")
            st.session_state.detected_language = detected_lang
            return result["text"]
    except Exception as exc:
        logger.error("Transcription error: %s", exc)
    return None


# ---------------------------------------------------------------------------
# STEP 1: INPUT
# ---------------------------------------------------------------------------
def page_input() -> None:
    """Render the initial symptom input page."""
    _inject_rtl_if_needed()

    st.title("🏥 CodeZero Emergency Triage")
    st.caption("AI-powered pre-hospital assessment — speak or type in any language")

    # Voice input
    st.subheader("🎤 Voice Input")
    if hasattr(st, "audio_input"):
        audio = st.audio_input("Tap the microphone and describe your symptoms")
        if audio is not None:
            st.audio(audio)
            transcribed = try_transcribe(audio)
            if transcribed:
                st.success(f"**Transcribed:** {transcribed}")
                if st.button(
                    "▶ Start triage with this",
                    type="primary",
                    use_container_width=True,
                    key="btn_voice",
                ):
                    do_process(transcribed)
            else:
                st.warning(
                    "Could not transcribe. Azure Speech may not be configured. "
                    "Please type your symptoms below."
                )
    else:
        st.info("Voice input requires Streamlit ≥ 1.41. Please type below.")

    st.divider()

    # Text input
    st.subheader("⌨️ Type Your Symptoms")
    complaint = st.text_area(
        "What's wrong?",
        placeholder="Example: I have severe chest pain and difficulty breathing",
        height=100,
    )
    st.caption("🌍 You can type in any language — it's auto-detected.")

    if st.button("▶ Start Triage", type="primary", use_container_width=True, key="btn_text"):
        if complaint and complaint.strip():
            do_process(complaint.strip())
        else:
            st.warning("Please describe your symptoms first.")

    st.divider()

    # Demo shortcuts
    st.subheader("⚡ Quick Demos")
    demo_col1, demo_col2 = st.columns(2)
    with demo_col1:
        if st.button("💔 Chest Pain", use_container_width=True, key="d1"):
            do_process("I have severe chest pain radiating to my left arm")
        if st.button("🧠 Stroke Symptoms", use_container_width=True, key="d2"):
            do_process("I suddenly can't move my right arm and my speech is slurred")
    with demo_col2:
        if st.button("🤕 Mild Headache", use_container_width=True, key="d3"):
            do_process("I have a mild headache that started yesterday")
        if st.button("🇩🇪 Demo Deutsch", use_container_width=True, key="d4"):
            do_process("Ich habe starke Brustschmerzen und Atemnot")
    # Arabic demo to test RTL
    if st.button("🇸🇦 Demo Arabic (RTL Test)", use_container_width=True, key="d5"):
        do_process("لدي ألم شديد في الصدر")


# ---------------------------------------------------------------------------
# STEP 2: QUESTIONS
# ---------------------------------------------------------------------------
def page_questions() -> None:
    """Render the dynamic follow-up questions page."""
    _inject_rtl_if_needed()

    st.title("🏥 Assessment Questions")
    st.info(f"**Your concern:** {st.session_state.complaint_text}")

    questions = st.session_state.questions
    idx = st.session_state.q_idx
    lang = st.session_state.detected_language

    # All questions answered — run final assessment
    if idx >= len(questions):
        with st.spinner("🔍 Analyzing your answers..."):
            if triage_engine:
                assessment = triage_engine.assess_triage(
                    st.session_state.complaint_english,
                    st.session_state.answers,
                )
            else:
                # Demo fallback
                assessment = {
                    "triage_level": TRIAGE_URGENT,
                    "assessment": "Demo mode — Azure OpenAI not configured.",
                    "red_flags": [],
                    "risk_score": 5,
                    "recommended_action": "Please consult a doctor.",
                    "time_sensitivity": "Soon",
                    "source_guidelines": [],
                    "suspected_conditions": [],
                }
            st.session_state.assessment = assessment
            st.session_state.step = "location"
            st.rerun()
        return

    total = len(questions)
    st.progress(idx / total, text=f"Question {idx + 1} of {total}")

    question = questions[idx]
    q_text: str = question.get("question", "")
    q_type: str = question.get("type", "yes_no")
    options: list[str] = question.get("options", ["Yes", "No"])

    st.markdown(f"### Q{idx + 1}: {t(q_text)}")

    answer = None
    if q_type == "scale":
        answer = st.select_slider("Select", options=options, key=f"q_{idx}")
    elif q_type == "multiple_choice":
        selected = st.multiselect(
            "Select all that apply",
            [t(opt) for opt in options],
            key=f"q_{idx}",
        )
        answer = ", ".join(selected) if selected else None
    else:
        answer = st.radio(
            "Select",
            [t(opt) for opt in options],
            key=f"q_{idx}",
            horizontal=True,
        )

    nav_col1, nav_col2 = st.columns(2)
    with nav_col1:
        if idx > 0 and st.button("⬅ Back", use_container_width=True, key="back"):
            st.session_state.q_idx -= 1
            if st.session_state.answers:
                st.session_state.answers.pop()
            st.rerun()
    with nav_col2:
        if st.button("Next ➡", type="primary", use_container_width=True, key="next"):
            if answer:
                # Translate answer back to English for backend processing
                eng_answer = str(answer)
                if translator:
                    try:
                        eng_answer = translator.translate_to_english(str(answer), lang)
                    except Exception:
                        pass
                st.session_state.answers.append({
                    "question": q_text,
                    "answer": eng_answer,
                    "original_answer": str(answer),
                })
                st.session_state.q_idx += 1
                st.rerun()
            else:
                st.warning("Please select an answer.")


# ---------------------------------------------------------------------------
# STEP 3: LOCATION & HOSPITAL SELECTION
# ---------------------------------------------------------------------------
def page_location() -> None:
    """Render the location and nearest hospital selection page."""
    _inject_rtl_if_needed()

    assessment = st.session_state.assessment
    level = assessment.get("triage_level", TRIAGE_URGENT)
    color = TRIAGE_COLORS.get(level, "🟠")
    summary = assessment.get("assessment", "")

    if level == TRIAGE_EMERGENCY:
        st.error(f"## {color} EMERGENCY\n\n{summary}")
    elif level == TRIAGE_URGENT:
        st.warning(f"## {color} URGENT\n\n{summary}")
    else:
        st.success(f"## {color} ROUTINE\n\n{summary}")

    st.subheader("📍 Find Nearest Hospitals")
    loc_col1, loc_col2 = st.columns(2)
    with loc_col1:
        lat = st.number_input("Latitude", value=48.78, format="%.4f")
    with loc_col2:
        lon = st.number_input("Longitude", value=9.18, format="%.4f")
    st.caption("💡 In production, GPS is captured automatically from your phone.")

    action_col1, action_col2 = st.columns(2)
    with action_col1:
        if st.button("🔍 Find Hospitals", type="primary", use_container_width=True, key="find"):
            with st.spinner("Searching for nearby hospitals..."):
                if maps_handler:
                    hospitals = maps_handler.find_nearest_hospitals(lat, lon, count=3)
                else:
                    hospitals = []
                st.session_state.nearby_hospitals = hospitals
                st.session_state.patient_lat = lat
                st.session_state.patient_lon = lon
                st.rerun()
    with action_col2:
        if st.button("⏭ Skip", use_container_width=True, key="skip"):
            _do_notify(None, None, None, None)
            st.session_state.step = "result"
            st.rerun()

    # Hospital list
    hospitals = st.session_state.nearby_hospitals
    if hospitals:
        st.divider()
        st.subheader("🏥 Nearest Emergency Hospitals")
        for i, hospital in enumerate(hospitals):
            badge = " ⭐ FASTEST" if i == 0 else ""
            card_text = (
                f"**#{i + 1} {hospital['name']}{badge}**\n\n"
                f"📏 {hospital['distance_km']} km · ⏱ {hospital['eta_minutes']} min\n\n"
                f"📍 {hospital.get('address', '')}"
            )
            if i == 0:
                st.success(card_text)
            else:
                st.info(card_text)

            if st.button(
                f"✅ Go to {hospital['name']}",
                key=f"sel_{i}",
                use_container_width=True,
            ):
                eta_info = {
                    "hospital_name": hospital["name"],
                    "hospital_lat": hospital["lat"],
                    "hospital_lon": hospital["lon"],
                    "eta_minutes": hospital["eta_minutes"],
                    "distance_km": hospital["distance_km"],
                    "address": hospital.get("address", ""),
                    "route_summary": hospital.get("route_summary", ""),
                    "traffic_delay_minutes": hospital.get("traffic_delay_minutes", 0),
                }
                st.session_state.selected_hospital = hospital
                st.session_state.eta_info = eta_info
                _do_notify(
                    st.session_state.patient_lat,
                    st.session_state.patient_lon,
                    eta_info,
                    hospital["name"],
                )
                st.session_state.step = "result"
                st.rerun()


def _do_notify(
    lat: float | None,
    lon: float | None,
    eta: dict | None,
    hospital_name: str | None,
) -> None:
    """Create patient record and push it to the hospital queue.

    Args:
        lat: Patient's latitude, or None.
        lon: Patient's longitude, or None.
        eta: ETA info dict, or None.
        hospital_name: Name of the destination hospital, or None.
    """
    location = {"lat": lat, "lon": lon} if lat is not None and lon is not None else None
    eta_minutes = eta.get("eta_minutes") if eta else None

    if triage_engine:
        record = triage_engine.create_patient_record(
            chief_complaint=st.session_state.complaint_english,
            assessment=st.session_state.assessment,
            language=st.session_state.detected_language,
            eta_minutes=eta_minutes,
            location=location,
        )
    else:
        record = {
            "patient_id": "DEMO-0000",
            "triage_level": TRIAGE_URGENT,
            "chief_complaint": st.session_state.complaint_text,
            "language": st.session_state.detected_language,
        }

    if hospital_name:
        record["destination_hospital"] = hospital_name

    if hospital_queue:
        hospital_queue.add_patient(record)

    st.session_state.patient_record = record


# ---------------------------------------------------------------------------
# STEP 4: RESULT
# ---------------------------------------------------------------------------
def page_result() -> None:
    """Render the final triage result and hospital notification page."""
    _inject_rtl_if_needed()

    assessment = st.session_state.assessment
    record = st.session_state.patient_record
    eta = st.session_state.eta_info
    level = assessment.get("triage_level", TRIAGE_URGENT)
    color = TRIAGE_COLORS.get(level, "🟠")
    summary = assessment.get("assessment", "")

    # Triage level banner
    if level == TRIAGE_EMERGENCY:
        st.error(f"## {color} EMERGENCY\n\n{summary}")
    elif level == TRIAGE_URGENT:
        st.warning(f"## {color} URGENT\n\n{summary}")
    else:
        st.success(f"## {color} ROUTINE\n\n{summary}")

    # Recommended action
    st.info(
        f"**📋 Recommended:** {assessment.get('recommended_action', '')}\n\n"
        f"**⏱ Time:** {assessment.get('time_sensitivity', '')}"
    )

    # Red flags
    flags = [f for f in assessment.get("red_flags", []) if f != "none_identified"]
    if flags:
        st.warning("**⚠️ Red Flags:** " + ", ".join(f.replace("_", " ").title() for f in flags))

    # Risk score
    risk = assessment.get("risk_score", 5)
    st.metric("Risk Score", f"{risk}/10")
    st.progress(risk / 10)

    # Hospital ETA card
    if eta:
        st.info(
            f"**🏥 {eta.get('hospital_name', '')}**\n\n"
            f"📍 {eta.get('address', '')}\n\n"
            f"📏 {eta.get('distance_km', '?')} km · ⏱ {eta.get('eta_minutes', '?')} min"
        )

    # Hospital notification confirmation
    if record:
        st.success(f"✅ Hospital notified! Patient ID: **{record.get('patient_id', '')}**")

    # Emergency call button (tel: link)
    if level == TRIAGE_EMERGENCY:
        st.markdown(
            '<div style="text-align:center; margin:1rem 0">'
            '<a href="tel:112" style="background:#dc2626; color:white; padding:16px 40px;'
            ' border-radius:12px; font-size:1.4rem; font-weight:700;'
            ' text-decoration:none; display:inline-block;">📞 CALL 112 NOW</a>'
            "</div>",
            unsafe_allow_html=True,
        )

    # Cited sources
    sources = assessment.get("source_guidelines", [])
    if sources:
        with st.expander("📋 Medical Sources Cited"):
            for source in sources:
                st.markdown(f"- {source}")

    # Patient answers summary
    if st.session_state.answers:
        with st.expander("📝 Your Answers"):
            for i, ans in enumerate(st.session_state.answers, 1):
                original = ans.get("original_answer", ans.get("answer", ""))
                st.markdown(f"**Q{i}:** {ans.get('question', '')} → **{original}**")

    st.divider()
    if st.button("🔄 New Triage", type="primary", use_container_width=True, key="restart"):
        reset()
        st.rerun()


# ---------------------------------------------------------------------------
# Sidebar — service status panel (Grup B: startup credential validator)
# ---------------------------------------------------------------------------
def render_sidebar() -> None:
    """Render sidebar with Azure service status indicators."""
    with st.sidebar:
        st.markdown("### 🏥 CodeZero")
        st.caption("AI-powered pre-hospital triage")
        st.divider()

        st.markdown("**Azure Services Status:**")
        for service_name, is_live in _svc_status.items():
            icon = "✅" if is_live else "⚠️"
            mode = "Live" if is_live else "Demo mode"
            st.markdown(f"{icon} {service_name} — *{mode}*")

        st.divider()

        # Current language indicator
        lang = st.session_state.get("detected_language", "en-US")
        rtl_note = " (RTL)" if lang in RTL_LOCALES else ""
        st.caption(f"🌍 Detected language: **{lang}**{rtl_note}")
        st.divider()

        st.caption("⚠️ Demo system only. Call 112/911 for real emergencies.")


# ---------------------------------------------------------------------------
# Main router
# ---------------------------------------------------------------------------
def main() -> None:
    """Route to the appropriate page based on session state step."""
    render_sidebar()

    step = st.session_state.step
    if step == "questions":
        page_questions()
    elif step == "location":
        page_location()
    elif step == "result":
        page_result()
    else:
        page_input()


if __name__ == "__main__":
    main()