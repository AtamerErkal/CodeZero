"""
Patient Triage App - CodeZero
Run: streamlit run ui/patient_app.py
"""
import logging
import sys
import tempfile
import os
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Imports (all resilient) ---
from src.hospital_queue import HospitalQueue
from src.knowledge_indexer import KnowledgeIndexer
from src.maps_handler import MapsHandler
from src.translator import Translator

try:
    from src.triage_engine import TRIAGE_COLORS, TRIAGE_EMERGENCY, TriageEngine
except ImportError:
    from src.triage_engine import *

try:
    from src.speech_handler import SpeechHandler
    _HAS_SPEECH = True
except Exception:
    _HAS_SPEECH = False

# --- Page config ---
st.set_page_config(page_title="CodeZero Triage", page_icon="🏥", layout="centered")

# --- Minimal CSS (works with forced light theme from config.toml) ---
st.markdown("""<style>
.block-container{max-width:720px}
.stButton>button{min-height:54px;font-size:1.05rem;border-radius:10px}
div[data-testid="stRadio"]>div>label{
    font-size:1.2rem!important;padding:12px 20px!important;
    border:2px solid #d0d5dd!important;border-radius:10px!important;
    min-height:48px!important;cursor:pointer!important;
}
div[data-testid="stRadio"]>div>label:hover{border-color:#2d4a9e!important;background:#f0f4ff!important}
</style>""", unsafe_allow_html=True)

# --- Services (cached, crash-proof) ---
@st.cache_resource
def load_services():
    parts = []
    try:
        ki = KnowledgeIndexer()
    except Exception:
        ki = None
    try:
        tr = Translator()
    except Exception:
        tr = None
    try:
        te = TriageEngine(knowledge_indexer=ki, translator=tr)
    except Exception:
        te = None
    try:
        mh = MapsHandler()
    except Exception:
        mh = None
    try:
        hq = HospitalQueue()
    except Exception:
        hq = None
    try:
        sh = SpeechHandler() if _HAS_SPEECH else None
    except Exception:
        sh = None
    return te, tr, mh, hq, sh

triage_engine, translator, maps_handler, hospital_queue, speech_handler = load_services()

# --- Session ---
_DEFAULTS = dict(
    step="input", complaint_text="", complaint_english="",
    detected_language="en-US", questions=[], answers=[],
    q_idx=0, assessment=None, patient_record=None,
    eta_info=None, nearby_hospitals=[], selected_hospital=None,
)
for k, v in _DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# --- Helpers ---
def t(text):
    lang = st.session_state.detected_language
    if not translator or lang.startswith("en"):
        return text
    try:
        return translator.translate_from_english(text, lang)
    except Exception:
        return text

def reset():
    for k, v in _DEFAULTS.items():
        st.session_state[k] = v

def do_process(text):
    """Detect language, translate, get questions, advance to questions step."""
    detected = None
    if translator:
        try:
            detected = translator.detect_language(text)
        except Exception:
            pass
    locale_map = {
        "de": "de-DE", "tr": "tr-TR", "ar": "ar-SA", "fr": "fr-FR",
        "es": "es-ES", "it": "it-IT", "pt": "pt-BR", "ru": "ru-RU",
        "zh-Hans": "zh-CN", "en": "en-US",
    }
    if detected:
        st.session_state.detected_language = locale_map.get(detected, "en-US")
    else:
        st.session_state.detected_language = "en-US"

    english = text
    if translator:
        try:
            english = translator.translate_to_english(text, st.session_state.detected_language)
        except Exception:
            pass
    st.session_state.complaint_text = text
    st.session_state.complaint_english = english
    if triage_engine:
        st.session_state.questions = triage_engine.generate_questions(english)
    else:
        st.session_state.questions = []
    st.session_state.q_idx = 0
    st.session_state.answers = []
    st.session_state.step = "questions"
    st.rerun()


def try_transcribe(audio):
    """Try Azure Speech transcription, return text or None."""
    if not speech_handler:
        return None
    if not getattr(speech_handler, "_initialized", False):
        return None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio.getvalue())
            path = tmp.name
        result = speech_handler.recognize_from_audio_file(path)
        os.unlink(path)
        if result and result.get("text"):
            lang = result.get("language", "en-US")
            st.session_state.detected_language = lang
            return result["text"]
    except Exception as e:
        logger.error("Transcription: %s", e)
    return None


# ===================================================================
# STEP 1: INPUT
# ===================================================================
def page_input():
    st.title("🏥 CodeZero Emergency Triage")
    st.caption("AI-powered pre-hospital assessment — speak or type in any language")

    # --- Voice ---
    st.subheader("🎤 Voice Input")
    if hasattr(st, "audio_input"):
        audio = st.audio_input("Tap the microphone and describe your symptoms")
        if audio is not None:
            st.audio(audio)
            text = try_transcribe(audio)
            if text:
                st.success("**Transcribed:** " + text)
                if st.button("▶ Start triage with this", type="primary", use_container_width=True, key="btn_voice"):
                    do_process(text)
            else:
                st.warning("Could not transcribe. Azure Speech may not be configured. Please type below.")
    else:
        st.info("Voice requires Streamlit ≥ 1.41. Please type below.")

    st.divider()

    # --- Text ---
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

    # --- Demo shortcuts ---
    st.subheader("Quick Demos")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("💔 Chest Pain", use_container_width=True, key="d1"):
            do_process("I have severe chest pain radiating to my left arm")
        if st.button("🧠 Stroke Symptoms", use_container_width=True, key="d2"):
            do_process("I suddenly can't move my right arm and my speech is slurred")
    with c2:
        if st.button("🤕 Mild Headache", use_container_width=True, key="d3"):
            do_process("I have a mild headache that started yesterday")
        if st.button("🇩🇪 Demo Deutsch", use_container_width=True, key="d4"):
            do_process("Ich habe starke Brustschmerzen und Atemnot")


# ===================================================================
# STEP 2: QUESTIONS
# ===================================================================
def page_questions():
    st.title("🏥 Assessment Questions")

    st.info("**Your concern:** " + st.session_state.complaint_text)

    questions = st.session_state.questions
    idx = st.session_state.q_idx
    lang = st.session_state.detected_language

    if idx >= len(questions):
        # All questions done — run assessment
        with st.spinner("🔍 Analyzing your answers..."):
            if triage_engine:
                assessment = triage_engine.assess_triage(
                    st.session_state.complaint_english, st.session_state.answers
                )
            else:
                assessment = {"triage_level": "URGENT", "assessment": "Demo mode", "red_flags": [], "risk_score": 5, "recommended_action": "See a doctor", "time_sensitivity": "Soon", "source_guidelines": [], "suspected_conditions": []}
            st.session_state.assessment = assessment
            st.session_state.step = "location"
            st.rerun()
        return

    total = len(questions)
    st.progress(idx / total, text="Question {} of {}".format(idx + 1, total))

    q = questions[idx]
    q_text = q.get("question", "")
    q_type = q.get("type", "yes_no")
    options = q.get("options", ["Yes", "No"])

    st.markdown("### Q{}: {}".format(idx + 1, t(q_text)))

    answer = None
    if q_type == "scale":
        answer = st.select_slider("Select", options=options, key="q_{}".format(idx))
    elif q_type == "multiple_choice":
        sel = st.multiselect("Select all that apply", [t(o) for o in options], key="q_{}".format(idx))
        answer = ", ".join(sel) if sel else None
    else:
        answer = st.radio("Select", [t(o) for o in options], key="q_{}".format(idx), horizontal=True)

    c1, c2 = st.columns(2)
    with c1:
        if idx > 0 and st.button("⬅ Back", use_container_width=True, key="back"):
            st.session_state.q_idx -= 1
            if st.session_state.answers:
                st.session_state.answers.pop()
            st.rerun()
    with c2:
        if st.button("Next ➡", type="primary", use_container_width=True, key="next"):
            if answer:
                eng = str(answer)
                if translator:
                    try:
                        eng = translator.translate_to_english(str(answer), lang)
                    except Exception:
                        pass
                st.session_state.answers.append(dict(
                    question=q_text, answer=eng, original_answer=str(answer),
                ))
                st.session_state.q_idx += 1
                st.rerun()
            else:
                st.warning("Please select an answer.")


# ===================================================================
# STEP 3: LOCATION & HOSPITALS
# ===================================================================
def page_location():
    assessment = st.session_state.assessment
    level = assessment.get("triage_level", "URGENT")
    color = TRIAGE_COLORS.get(level, "🟠")

    if level == "EMERGENCY":
        st.error("## {} EMERGENCY\n\n{}".format(color, assessment.get("assessment", "")))
    elif level == "URGENT":
        st.warning("## {} URGENT\n\n{}".format(color, assessment.get("assessment", "")))
    else:
        st.success("## {} ROUTINE\n\n{}".format(color, assessment.get("assessment", "")))

    st.subheader("📍 Find Nearest Hospitals")
    c1, c2 = st.columns(2)
    with c1:
        lat = st.number_input("Latitude", value=48.78, format="%.4f")
    with c2:
        lon = st.number_input("Longitude", value=9.18, format="%.4f")
    st.caption("💡 In production, GPS is captured automatically from your phone.")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔍 Find Hospitals", type="primary", use_container_width=True, key="find"):
            with st.spinner("Searching..."):
                if maps_handler:
                    hospitals = maps_handler.find_nearest_hospitals(lat, lon, count=3)
                else:
                    hospitals = []
                st.session_state.nearby_hospitals = hospitals
                st.session_state.patient_lat = lat
                st.session_state.patient_lon = lon
                st.rerun()
    with col2:
        if st.button("⏭ Skip", use_container_width=True, key="skip"):
            do_notify(None, None, None, None)
            st.session_state.step = "result"
            st.rerun()

    # Show hospitals
    hospitals = st.session_state.nearby_hospitals
    if hospitals:
        st.divider()
        st.subheader("🏥 Nearest Emergency Hospitals")
        for i, h in enumerate(hospitals):
            badge = " ⭐ FASTEST" if i == 0 else ""
            if i == 0:
                st.success(
                    "**#{} {}{}**\n\n📏 {} km · ⏱ {} min\n\n📍 {}".format(
                        i + 1, h["name"], badge, h["distance_km"], h["eta_minutes"], h.get("address", "")
                    )
                )
            else:
                st.info(
                    "**#{} {}**\n\n📏 {} km · ⏱ {} min\n\n📍 {}".format(
                        i + 1, h["name"], h["distance_km"], h["eta_minutes"], h.get("address", "")
                    )
                )
            if st.button("✅ Go to {}".format(h["name"]), key="sel_{}".format(i), use_container_width=True):
                st.session_state.selected_hospital = h
                st.session_state.eta_info = dict(
                    hospital_name=h["name"], hospital_lat=h["lat"],
                    hospital_lon=h["lon"], eta_minutes=h["eta_minutes"],
                    distance_km=h["distance_km"], address=h.get("address", ""),
                    route_summary=h.get("route_summary", ""),
                    traffic_delay_minutes=h.get("traffic_delay_minutes", 0),
                )
                do_notify(
                    st.session_state.get("patient_lat"),
                    st.session_state.get("patient_lon"),
                    st.session_state.eta_info, h["name"],
                )
                st.session_state.step = "result"
                st.rerun()


def do_notify(lat, lon, eta, hospital_name):
    loc = dict(lat=lat, lon=lon) if lat and lon else None
    eta_min = eta.get("eta_minutes") if eta else None
    if triage_engine:
        record = triage_engine.create_patient_record(
            chief_complaint=st.session_state.complaint_english,
            assessment=st.session_state.assessment,
            language=st.session_state.detected_language,
            eta_minutes=eta_min, location=loc,
        )
    else:
        record = dict(patient_id="DEMO-0000", triage_level="URGENT")
    if hospital_name:
        record["destination_hospital"] = hospital_name
    if hospital_queue:
        hospital_queue.add_patient(record)
    st.session_state.patient_record = record


# ===================================================================
# STEP 4: RESULT
# ===================================================================
def page_result():
    assessment = st.session_state.assessment
    record = st.session_state.patient_record
    eta = st.session_state.eta_info
    level = assessment.get("triage_level", "URGENT")
    color = TRIAGE_COLORS.get(level, "🟠")

    # Level banner
    if level == "EMERGENCY":
        st.error("## {} EMERGENCY\n\n{}".format(color, assessment.get("assessment", "")))
    elif level == "URGENT":
        st.warning("## {} URGENT\n\n{}".format(color, assessment.get("assessment", "")))
    else:
        st.success("## {} ROUTINE\n\n{}".format(color, assessment.get("assessment", "")))

    # Action
    st.info("**📋 Recommended:** {}\n\n**⏱ Time:** {}".format(
        assessment.get("recommended_action", ""), assessment.get("time_sensitivity", "")
    ))

    # Red flags
    flags = assessment.get("red_flags", [])
    if flags and flags != ["none_identified"]:
        st.warning("**⚠️ Red Flags:** " + ", ".join(f.replace("_", " ").title() for f in flags))

    # Risk
    risk = assessment.get("risk_score", 5)
    st.metric("Risk Score", "{}/10".format(risk))
    st.progress(risk / 10)

    # Hospital
    if eta:
        st.info(
            "**🏥 {}**\n\n📍 {}\n\n📏 {} km · ⏱ {} min".format(
                eta.get("hospital_name", ""), eta.get("address", ""),
                eta.get("distance_km", "?"), eta.get("eta_minutes", "?"),
            )
        )

    # Confirmation
    if record:
        st.success("✅ Hospital notified! ID: **{}**".format(record.get("patient_id", "")))

    # Emergency call
    if level == "EMERGENCY":
        st.markdown(
            '<div style="text-align:center;margin:1rem 0">'
            '<a href="tel:112" style="background:#dc2626;color:white;padding:16px 40px;'
            'border-radius:12px;font-size:1.4rem;font-weight:700;text-decoration:none">'
            '📞 CALL 112 NOW</a></div>',
            unsafe_allow_html=True,
        )

    # Sources
    sources = assessment.get("source_guidelines", [])
    if sources:
        with st.expander("📋 Sources"):
            for s in sources:
                st.markdown("- " + s)

    # Answer summary
    if st.session_state.answers:
        with st.expander("📝 Your Answers"):
            for i, a in enumerate(st.session_state.answers, 1):
                st.markdown("**Q{}:** {} → **{}**".format(i, a.get("question", ""), a.get("original_answer", a.get("answer", ""))))

    st.divider()
    if st.button("🔄 New Triage", type="primary", use_container_width=True, key="restart"):
        reset()
        st.rerun()


# ===================================================================
# MAIN
# ===================================================================
def main():
    step = st.session_state.step
    if step == "questions":
        page_questions()
    elif step == "location":
        page_location()
    elif step == "result":
        page_result()
    else:
        page_input()

    with st.sidebar:
        st.markdown("### 🏥 CodeZero")
        st.caption("AI-powered pre-hospital triage")
        st.divider()
        st.markdown("**Azure AI Services:**")
        for svc in ["OpenAI (GPT-4)", "AI Search (RAG)", "Speech Services",
                     "Translator", "Maps", "Content Safety"]:
            st.markdown("• " + svc)
        st.divider()
        st.caption("⚠️ Demo only. Call 112/911 for real emergencies.")


if __name__ == "__main__":
    main()