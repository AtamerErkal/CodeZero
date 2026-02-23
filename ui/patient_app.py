"""
Patient Triage App (Streamlit)
==============================
Mobile-responsive patient-facing web application for AI-powered
pre-hospital triage. Supports voice input with auto language detection,
dynamic follow-up questions, and real-time hospital notification.

Run with: streamlit run ui/patient_app.py

AI-102 Concepts demonstrated:
  - Azure OpenAI (GPT-4) for conversational AI and triage reasoning
  - Azure Speech Services for voice input with language auto-detection
  - Azure Translator for multilingual support
  - Azure AI Search + Document Intelligence for RAG grounding
  - Azure Maps for ETA calculation
  - Agentic AI: dynamic multi-step questioning workflow
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import streamlit as st

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.hospital_queue import HospitalQueue
from src.knowledge_indexer import KnowledgeIndexer
from src.maps_handler import MapsHandler
from src.translator import Translator
from src.triage_engine import (
    TRIAGE_COLORS,
    TRIAGE_EMERGENCY,
    TriageEngine,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Emergency Triage",
    page_icon="🏥",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """<style>
    .main .block-container {padding:1rem;max-width:700px}
    .triage-emergency {background:linear-gradient(135deg,#ff4444,#cc0000);color:#fff;
        padding:1.5rem;border-radius:12px;margin:1rem 0;text-align:center}
    .triage-urgent {background:linear-gradient(135deg,#ff8800,#cc6600);color:#fff;
        padding:1.5rem;border-radius:12px;margin:1rem 0;text-align:center}
    .triage-routine {background:linear-gradient(135deg,#44bb44,#228822);color:#fff;
        padding:1.5rem;border-radius:12px;margin:1rem 0;text-align:center}
    .eta-card {background:#1a1a2e;color:#e0e0e0;padding:1.5rem;border-radius:12px;
        margin:1rem 0;border-left:4px solid #0077ff}
    .question-card {background:#f8f9fa;padding:1rem;border-radius:8px;margin:.5rem 0;
        border-left:3px solid #0077ff}
    .rtl-text {direction:rtl;text-align:right}
    .stButton>button {min-height:48px;font-size:1.1rem}
    </style>""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Cached service initialization
# ---------------------------------------------------------------------------

@st.cache_resource
def init_services():
    """Initialize all backend services (cached across reruns)."""
    ki = KnowledgeIndexer()
    tr = Translator()
    te = TriageEngine(knowledge_indexer=ki, translator=tr)
    mh = MapsHandler()
    hq = HospitalQueue()
    return te, tr, mh, hq

triage_engine, translator, maps_handler, hospital_queue = init_services()

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

DEFAULTS = {
    "step": "input",
    "complaint_text": "",
    "complaint_english": "",
    "detected_language": "en-US",
    "questions": [],
    "answers": [],
    "q_idx": 0,
    "assessment": None,
    "patient_record": None,
    "eta_info": None,
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def t(text: str) -> str:
    """Translate English → patient language."""
    lang = st.session_state.detected_language
    if lang.startswith("en"):
        return text
    return translator.translate_from_english(text, lang)


def is_rtl() -> bool:
    return st.session_state.detected_language.startswith(("ar", "he", "fa", "ur"))


def reset():
    """Reset the session to start over."""
    for k, v in DEFAULTS.items():
        st.session_state[k] = v


# ---------------------------------------------------------------------------
# STEP 1: Patient input
# ---------------------------------------------------------------------------

def render_input():
    st.markdown("## 🏥 " + t("Emergency Triage"))
    st.markdown(t("Tell us how you're feeling. Type or speak your symptoms."))

    # Voice input section
    st.markdown("#### 🎤 " + t("Voice Input"))
    st.caption(t("🌍 Speak in any language — we will auto-detect it."))
    audio_value = st.audio_input(
        t("Tap the microphone and describe your symptoms"),
        key="voice_input",
    )
    if audio_value is not None:
        st.audio(audio_value)
        st.info(
            t(
                "🔊 Audio recorded! In production, this would be sent to Azure Speech "
                "Services for transcription with automatic language detection. "
                "For this demo, please also type your symptoms below."
            )
        )

    st.markdown("---")

    # Text input (always available)
    st.markdown("#### ⌨️ " + t("Text Input"))
    complaint = st.text_area(
        t("Describe your symptoms"),
        placeholder=t("Example: I have severe chest pain and difficulty breathing"),
        height=120,
    )
    st.caption(t("🌍 You can type in any language — we will auto-detect it."))

    c1, c2 = st.columns(2)
    with c1:
        if st.button(t("▶ Start Triage"), type="primary", use_container_width=True):
            if complaint and complaint.strip():
                _process(complaint.strip())
            else:
                st.warning(t("Please describe your symptoms first."))
    with c2:
        if st.button("🇩🇪 Demo (German)", use_container_width=True):
            _process("Ich habe starke Brustschmerzen und Atemnot")

    st.markdown("---")
    st.markdown("##### " + t("Quick demo scenarios:"))
    dc = st.columns(2)
    with dc[0]:
        if st.button("💔 Chest Pain", use_container_width=True):
            _process("I have severe chest pain radiating to my left arm")
    with dc[1]:
        if st.button("🧠 Stroke", use_container_width=True):
            _process("I suddenly can't move my right arm and my speech is slurred")
    dc2 = st.columns(2)
    with dc2[0]:
        if st.button("🤕 Headache", use_container_width=True):
            _process("I have a mild headache that started yesterday")
    with dc2[1]:
        if st.button("🤢 Stomach Pain", use_container_width=True):
            _process("I have severe abdominal pain and I've been vomiting")


def _process(text: str):
    """Detect language, translate, generate questions."""
    with st.spinner(t("Analyzing your symptoms...")):
        detected = translator.detect_language(text)
        locale_map = {
            "de": "de-DE", "tr": "tr-TR", "ar": "ar-SA", "fr": "fr-FR",
            "es": "es-ES", "it": "it-IT", "pt": "pt-BR", "ru": "ru-RU",
            "zh-Hans": "zh-CN", "en": "en-US",
        }
        st.session_state.detected_language = (
            locale_map.get(detected, f"{detected}-{detected.upper()}")
            if detected
            else "en-US"
        )
        english = translator.translate_to_english(text, st.session_state.detected_language)
        st.session_state.complaint_text = text
        st.session_state.complaint_english = english
        st.session_state.questions = triage_engine.generate_questions(english)
        st.session_state.q_idx = 0
        st.session_state.answers = []
        st.session_state.step = "questions"
        st.rerun()


# ---------------------------------------------------------------------------
# STEP 2: Follow-up questions
# ---------------------------------------------------------------------------

def render_questions():
    lang = st.session_state.detected_language
    st.markdown("## 🏥 " + t("Assessment Questions"))
    st.info(f"**{t('Your concern')}:** {st.session_state.complaint_text}")
    if not lang.startswith("en"):
        st.caption(f"🌍 {t('Detected language')}: {lang}")

    questions = st.session_state.questions
    idx = st.session_state.q_idx

    if idx >= len(questions):
        _run_assessment()
        return

    total = len(questions)
    st.progress(idx / total, text=t(f"Question {idx + 1} of {total}"))

    q = questions[idx]
    q_text = q.get("question", "")
    q_type = q.get("type", "yes_no")
    options = q.get("options", ["Yes", "No"])

    rtl_cls = "rtl-text" if is_rtl() else ""
    st.markdown(
        f'<div class="question-card {rtl_cls}"><strong>{t("Question")} {idx+1}:</strong>'
        f"<br>{t(q_text)}</div>",
        unsafe_allow_html=True,
    )

    answer = None
    if q_type == "yes_no":
        answer = st.radio("ans", [t(o) for o in options], key=f"q{idx}", horizontal=True, label_visibility="collapsed")
    elif q_type == "scale":
        answer = st.select_slider(t("Select value"), options=options, key=f"q{idx}")
    elif q_type == "multiple_choice":
        sel = st.multiselect(t("Select all that apply"), [t(o) for o in options], key=f"q{idx}")
        answer = ", ".join(sel) if sel else t("None")
    else:
        answer = st.radio("ans", [t(o) for o in options], key=f"q{idx}", label_visibility="collapsed")

    c1, c2 = st.columns(2)
    with c1:
        if idx > 0 and st.button(t("⬅ Back"), use_container_width=True):
            st.session_state.q_idx -= 1
            if st.session_state.answers:
                st.session_state.answers.pop()
            st.rerun()
    with c2:
        if st.button(t("Next ➡"), type="primary", use_container_width=True):
            if answer:
                eng_ans = translator.translate_to_english(str(answer), lang)
                st.session_state.answers.append({"question": q_text, "answer": eng_ans, "original_answer": str(answer)})
                st.session_state.q_idx += 1
                st.rerun()
            else:
                st.warning(t("Please provide an answer to continue."))


def _run_assessment():
    with st.spinner(t("🔍 Analyzing your symptoms...")):
        assessment = triage_engine.assess_triage(st.session_state.complaint_english, st.session_state.answers)
        st.session_state.assessment = assessment
        st.session_state.step = "location"
        st.rerun()


# ---------------------------------------------------------------------------
# STEP 3: Location & ETA
# ---------------------------------------------------------------------------

def render_location():
    assessment = st.session_state.assessment
    level = assessment.get("triage_level", "URGENT")
    color = TRIAGE_COLORS.get(level, "🟠")
    css = f"triage-{level.lower()}"

    st.markdown("## 📍 " + t("Location & Hospital"))
    st.markdown(
        f'<div class="{css}"><h3>{color} {t(level)}</h3><p>{t(assessment.get("assessment",""))}</p></div>',
        unsafe_allow_html=True,
    )

    st.markdown("### " + t("Share your location for ETA calculation"))

    c1, c2 = st.columns(2)
    with c1:
        lat = st.number_input(t("Latitude"), value=48.78, min_value=-90.0, max_value=90.0, format="%.4f")
    with c2:
        lon = st.number_input(t("Longitude"), value=9.18, min_value=-180.0, max_value=180.0, format="%.4f")

    st.caption(t("💡 In a production app, GPS location would be captured automatically via the browser."))

    c1, c2 = st.columns(2)
    with c1:
        if st.button(t("📍 Calculate ETA"), type="primary", use_container_width=True):
            with st.spinner(t("Calculating route...")):
                eta = maps_handler.calculate_eta(lat, lon)
                st.session_state.eta_info = eta
                _notify_hospital(lat, lon, eta)
                st.session_state.step = "result"
                st.rerun()
    with c2:
        if st.button(t("⏭ Skip Location"), use_container_width=True):
            st.session_state.eta_info = None
            _notify_hospital(None, None, None)
            st.session_state.step = "result"
            st.rerun()


def _notify_hospital(lat, lon, eta):
    """Create patient record and add to hospital queue."""
    location = {"lat": lat, "lon": lon} if lat and lon else None
    eta_min = eta.get("eta_minutes") if eta else None
    record = triage_engine.create_patient_record(
        chief_complaint=st.session_state.complaint_english,
        assessment=st.session_state.assessment,
        language=st.session_state.detected_language,
        eta_minutes=eta_min,
        location=location,
    )
    hospital_queue.add_patient(record)
    st.session_state.patient_record = record


# ---------------------------------------------------------------------------
# STEP 4: Final result
# ---------------------------------------------------------------------------

def render_result():
    assessment = st.session_state.assessment
    record = st.session_state.patient_record
    eta = st.session_state.eta_info
    level = assessment.get("triage_level", "URGENT")
    color = TRIAGE_COLORS.get(level, "🟠")
    css = f"triage-{level.lower()}"

    st.markdown("## 🏥 " + t("Triage Result"))

    # Triage level banner
    st.markdown(
        f'<div class="{css}">'
        f'<h2>{color} {t(level)}</h2>'
        f'<p style="font-size:1.1rem">{t(assessment.get("assessment",""))}</p>'
        f"</div>",
        unsafe_allow_html=True,
    )

    # Recommended action
    st.markdown("### " + t("Recommended Action"))
    st.warning(t(assessment.get("recommended_action", "")))
    st.markdown(f"⏱ **{t('Time sensitivity')}:** {t(assessment.get('time_sensitivity',''))}")

    # Red flags
    flags = assessment.get("red_flags", [])
    if flags and flags != ["none_identified"]:
        st.markdown("### " + t("Identified Red Flags"))
        for flag in flags:
            st.markdown(f"- 🚩 {t(flag.replace('_', ' ').title())}")

    # Risk score
    risk = assessment.get("risk_score", 5)
    st.markdown(f"### {t('Risk Score')}: **{risk}/10**")
    st.progress(risk / 10)

    # ETA information
    if eta:
        st.markdown(
            f'<div class="eta-card">'
            f'<h4>🗺 {t("Route to Hospital")}</h4>'
            f'<p><strong>{eta.get("hospital_name","Hospital")}</strong></p>'
            f'<p>📏 {eta.get("distance_km","?")} km &nbsp;|&nbsp; '
            f'⏱ {eta.get("eta_minutes","?")} {t("minutes")}</p>'
            f'<p><em>{t("Route")}:  {eta.get("route_summary","")}</em></p>'
            f"</div>",
            unsafe_allow_html=True,
        )

    # Hospital notification confirmation
    if record:
        st.success(t("✅ Hospital has been notified. Your patient ID is:") + f" **{record.get('patient_id','')}**")

    # Emergency call button
    if level == TRIAGE_EMERGENCY:
        st.markdown("---")
        st.markdown(
            f'<div style="text-align:center;padding:1rem">'
            f'<a href="tel:112" style="background:#ff0000;color:white;padding:1rem 2rem;'
            f'border-radius:8px;text-decoration:none;font-size:1.5rem;font-weight:bold">'
            f'📞 {t("CALL 112 NOW")}</a></div>',
            unsafe_allow_html=True,
        )

    # Source guidelines
    sources = assessment.get("source_guidelines", [])
    if sources:
        with st.expander(t("📋 Source Guidelines")):
            for src in sources:
                st.markdown(f"- {src}")

    # Answers review
    if st.session_state.answers:
        with st.expander(t("📝 Your Answers Summary")):
            for i, ans in enumerate(st.session_state.answers, 1):
                st.markdown(
                    f"**Q{i}:** {t(ans.get('question', ''))}\n\n"
                    f"**A:** {ans.get('original_answer', ans.get('answer', ''))}"
                )
                st.markdown("---")

    st.markdown("---")
    if st.button(t("🔄 Start New Triage"), type="primary", use_container_width=True):
        reset()
        st.rerun()


# ---------------------------------------------------------------------------
# Main routing
# ---------------------------------------------------------------------------

def main():
    step = st.session_state.step
    if step == "input":
        render_input()
    elif step == "questions":
        render_questions()
    elif step == "location":
        render_location()
    elif step == "result":
        render_result()
    else:
        render_input()

    # Sidebar info
    with st.sidebar:
        st.markdown("### ℹ️ About")
        st.markdown(
            "This is an AI-powered pre-hospital triage system. "
            "It uses Azure AI services for intelligent symptom assessment."
        )
        st.markdown("---")
        st.markdown("**Azure Services Used:**")
        st.markdown("- Azure OpenAI (GPT-4)")
        st.markdown("- Azure AI Search (RAG)")
        st.markdown("- Azure Translator")
        st.markdown("- Azure Speech Services")
        st.markdown("- Azure Maps")
        st.markdown("- Azure Content Safety")
        st.markdown("---")
        st.caption("⚠️ This is a demo. Always call emergency services for real emergencies.")


if __name__ == "__main__":
    main()