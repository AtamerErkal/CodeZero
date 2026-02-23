"""
Patient Triage App — CodeZero
"""

from __future__ import annotations
import logging, sys, tempfile, os
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Imports (resilient)
# ---------------------------------------------------------------------------
from src.hospital_queue import HospitalQueue
from src.knowledge_indexer import KnowledgeIndexer
from src.maps_handler import MapsHandler
from src.translator import Translator

try:
    from src.triage_engine import TRIAGE_COLORS, TRIAGE_EMERGENCY, TriageEngine
except ImportError:
    from src.triage_engine import *  # noqa

try:
    from src.speech_handler import SpeechHandler
    _SPEECH_AVAILABLE = True
except Exception:
    _SPEECH_AVAILABLE = False

# ---------------------------------------------------------------------------
# Page config — MUST be first Streamlit command
# ---------------------------------------------------------------------------
st.set_page_config(page_title="CodeZero Triage", page_icon="🏥", layout="centered")

# ---------------------------------------------------------------------------
# Professional Medical Theme
# ---------------------------------------------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap');

/* Global reset */
html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif !important;
}
.main { background: #f7f8fc !important; }
header[data-testid="stHeader"] { background: #f7f8fc !important; }
section[data-testid="stSidebar"] { background: #eef0f5 !important; }

.block-container { max-width: 720px; padding: 1.5rem 1rem !important; }

/* Typography */
h1, h2, h3, h4 { color: #1b2559 !important; font-weight: 700 !important; }
p, li, span, div, label { color: #333 !important; }

/* --- Custom components --- */
.app-header {
    background: linear-gradient(135deg, #1b2559 0%, #2d4a9e 100%);
    color: white; padding: 1.8rem 1.5rem; border-radius: 16px;
    margin-bottom: 1.5rem; text-align: center;
}
.app-header h1 { color: white !important; font-size: 1.6rem; margin: 0; }
.app-header p { color: rgba(255,255,255,0.85) !important; margin: 0.3rem 0 0; font-size: 0.95rem; }

.card {
    background: white; border-radius: 14px; padding: 1.5rem;
    box-shadow: 0 2px 12px rgba(0,0,0,0.06); margin: 0.8rem 0;
    border: 1px solid #e8eaf0;
}

.level-emergency {
    background: linear-gradient(135deg, #dc2626, #b91c1c);
    color: white; padding: 1.5rem; border-radius: 14px;
    text-align: center; margin: 1rem 0;
}
.level-urgent {
    background: linear-gradient(135deg, #ea580c, #c2410c);
    color: white; padding: 1.5rem; border-radius: 14px;
    text-align: center; margin: 1rem 0;
}
.level-routine {
    background: linear-gradient(135deg, #16a34a, #15803d);
    color: white; padding: 1.5rem; border-radius: 14px;
    text-align: center; margin: 1rem 0;
}
.level-emergency *, .level-urgent *, .level-routine * { color: white !important; }

.q-card {
    background: #eef3ff; border-left: 4px solid #2d4a9e;
    padding: 1.2rem 1.5rem; border-radius: 0 12px 12px 0;
    margin: 0.5rem 0; font-size: 1.15rem; color: #1b2559 !important;
}

.hospital-card {
    background: white; border: 2px solid #e0e4ec; border-radius: 12px;
    padding: 1.2rem; margin: 0.6rem 0; transition: border-color 0.2s;
}
.hospital-card:hover { border-color: #2d4a9e; }
.hospital-best { border-color: #16a34a; background: #f0fdf4; }

.eta-box {
    background: #1b2559; color: #e8eaf0; padding: 1.5rem;
    border-radius: 14px; margin: 1rem 0;
}
.eta-box * { color: #e8eaf0 !important; }

/* Big accessible buttons */
.stButton > button {
    min-height: 56px !important; font-size: 1.1rem !important;
    font-weight: 600 !important; border-radius: 12px !important;
}

/* Huge radio/choice buttons for sick patients */
div[data-testid="stRadio"] > div { gap: 8px !important; }
div[data-testid="stRadio"] > div > label {
    font-size: 1.25rem !important; font-weight: 500 !important;
    padding: 14px 22px !important; border: 2px solid #d1d5e0 !important;
    border-radius: 12px !important; background: white !important;
    color: #1b2559 !important; min-height: 52px !important;
    display: flex !important; align-items: center !important;
    cursor: pointer !important; transition: all 0.15s !important;
}
div[data-testid="stRadio"] > div > label:hover {
    border-color: #2d4a9e !important; background: #eef3ff !important;
}

/* Multiselect */
div[data-testid="stMultiSelect"] [data-baseweb="tag"] {
    font-size: 1.05rem; padding: 6px 14px; border-radius: 8px;
}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Services
# ---------------------------------------------------------------------------
@st.cache_resource
def init_services():
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
        sh = SpeechHandler() if _SPEECH_AVAILABLE else None
    except Exception:
        sh = None
    return te, tr, mh, hq, sh

triage_engine, translator, maps_handler, hospital_queue, speech_handler = init_services()

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
DEFAULTS = {
    "step": "input", "complaint_text": "", "complaint_english": "",
    "detected_language": "en-US", "questions": [], "answers": [],
    "q_idx": 0, "assessment": None, "patient_record": None,
    "eta_info": None, "nearby_hospitals": [], "selected_hospital": None,
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def t(text):
    lang = st.session_state.detected_language
    if not translator or lang.startswith("en"):
        return text
    return translator.translate_from_english(text, lang)

def reset():
    for k, v in DEFAULTS.items():
        st.session_state[k] = v

def _process(text):
    """Detect language, translate, generate questions."""
    with st.spinner(t("Analyzing your symptoms...")):
        detected = translator.detect_language(text) if translator else None
        locale_map = {
            "de": "de-DE", "tr": "tr-TR", "ar": "ar-SA", "fr": "fr-FR",
            "es": "es-ES", "it": "it-IT", "pt": "pt-BR", "ru": "ru-RU",
            "zh-Hans": "zh-CN", "en": "en-US",
        }
        st.session_state.detected_language = (
            locale_map.get(detected, f"{detected}-{detected.upper()}") if detected else "en-US"
        )
        english = translator.translate_to_english(text, st.session_state.detected_language) if translator else text
        st.session_state.complaint_text = text
        st.session_state.complaint_english = english
        st.session_state.questions = triage_engine.generate_questions(english) if triage_engine else []
        st.session_state.q_idx = 0
        st.session_state.answers = []
        st.session_state.step = "questions"
        st.rerun()

# ---------------------------------------------------------------------------
# STEP 1: Input
# ---------------------------------------------------------------------------
def render_input():
    st.markdown(
        '<div class="app-header"><h1>🏥 CodeZero Emergency Triage</h1>'
        '<p>AI-powered pre-hospital assessment • Speak or type in any language</p></div>',
        unsafe_allow_html=True,
    )

    # --- Voice Input ---
    st.markdown("##### 🎤 " + t("Speak your symptoms"))
    has_audio_input = hasattr(st, "audio_input")

    if has_audio_input:
        audio_value = st.audio_input(t("Tap to record"), key="voice_input")
        if audio_value is not None:
            st.audio(audio_value)
            transcribed = _try_transcribe(audio_value)
            if transcribed:
                st.success(f"**{t('Heard')}:** {transcribed}")
                if st.button(t("▶ Start triage with this"), type="primary", use_container_width=True, key="use_voice"):
                    _process(transcribed)
                    return
            else:
                st.warning(t("Could not understand audio. Please try again or type below."))
    else:
        st.info(t("Voice requires Streamlit ≥ 1.41. Please type below."))

    st.markdown("---")

    # --- Text Input ---
    st.markdown("##### ⌨️ " + t("Type your symptoms"))
    complaint = st.text_area(
        t("What's wrong?"),
        placeholder=t("Example: I have severe chest pain and difficulty breathing"),
        height=110, label_visibility="collapsed",
    )
    st.caption(t("🌍 Type in any language — auto-detected."))

    if st.button(t("▶ Start Triage"), type="primary", use_container_width=True, key="start_text"):
        if complaint and complaint.strip():
            _process(complaint.strip())
        else:
            st.warning(t("Please describe your symptoms."))

    st.markdown("---")
    st.markdown("##### " + t("Quick demos"))
    cols = st.columns(2)
    with cols[0]:
        if st.button("💔 " + t("Chest Pain"), use_container_width=True, key="d1"):
            _process("I have severe chest pain radiating to my left arm")
        if st.button("🧠 " + t("Stroke"), use_container_width=True, key="d2"):
            _process("I suddenly can't move my right arm and my speech is slurred")
    with cols[1]:
        if st.button("🤕 " + t("Headache"), use_container_width=True, key="d3"):
            _process("I have a mild headache that started yesterday")
        if st.button("🇩🇪 Demo Deutsch", use_container_width=True, key="d4"):
            _process("Ich habe starke Brustschmerzen und Atemnot")


def _try_transcribe(audio_value) -> str | None:
    """Attempt to transcribe audio via Azure Speech."""
    if not speech_handler or not speech_handler._initialized:
        return None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_value.getvalue())
            tmp_path = tmp.name
        result = speech_handler.recognize_from_audio_file(tmp_path)
        os.unlink(tmp_path)
        if result and result.get("text"):
            detected = result.get("language", "en-US")
            st.session_state.detected_language = detected
            return result["text"]
    except Exception as e:
        logger.error("Transcription error: %s", e)
    return None


# ---------------------------------------------------------------------------
# STEP 2: Questions
# ---------------------------------------------------------------------------
def render_questions():
    lang = st.session_state.detected_language

    st.markdown('<div class="app-header"><h1>🏥 Assessment Questions</h1></div>', unsafe_allow_html=True)

    st.markdown(
        f'<div class="card"><strong>{t("Your concern")}:</strong> {st.session_state.complaint_text}</div>',
        unsafe_allow_html=True,
    )

    questions = st.session_state.questions
    idx = st.session_state.q_idx

    if idx >= len(questions):
        with st.spinner(t("🔍 Analyzing your answers...")):
            assessment = triage_engine.assess_triage(st.session_state.complaint_english, st.session_state.answers)
            st.session_state.assessment = assessment
            st.session_state.step = "location"
            st.rerun()
        return

    total = len(questions)
    st.progress((idx) / total, text=t(f"Question {idx + 1} of {total}"))

    q = questions[idx]
    q_text = q.get("question", "")
    q_type = q.get("type", "yes_no")
    options = q.get("options", ["Yes", "No"])

    st.markdown(f'<div class="q-card"><strong>Q{idx+1}:</strong> {t(q_text)}</div>', unsafe_allow_html=True)

    answer = None
    if q_type == "yes_no":
        answer = st.radio(
            "answer", [t(o) for o in options],
            key=f"q{idx}", horizontal=True, label_visibility="collapsed",
        )
    elif q_type == "scale":
        answer = st.select_slider(t("Select"), options=options, key=f"q{idx}")
    elif q_type == "multiple_choice":
        sel = st.multiselect(t("Select all that apply"), [t(o) for o in options], key=f"q{idx}")
        answer = ", ".join(sel) if sel else None
    else:
        answer = st.radio(
            "answer", [t(o) for o in options],
            key=f"q{idx}", horizontal=True, label_visibility="collapsed",
        )

    c1, c2 = st.columns(2)
    with c1:
        if idx > 0 and st.button(t("⬅ Back"), use_container_width=True, key="back"):
            st.session_state.q_idx -= 1
            if st.session_state.answers:
                st.session_state.answers.pop()
            st.rerun()
    with c2:
        if st.button(t("Next ➡"), type="primary", use_container_width=True, key="next"):
            if answer:
                eng_ans = translator.translate_to_english(str(answer), lang) if translator else str(answer)
                st.session_state.answers.append({
                    "question": q_text, "answer": eng_ans, "original_answer": str(answer),
                })
                st.session_state.q_idx += 1
                st.rerun()
            else:
                st.warning(t("Please select an answer."))


# ---------------------------------------------------------------------------
# STEP 3: Location & Hospital Selection
# ---------------------------------------------------------------------------
def render_location():
    assessment = st.session_state.assessment
    level = assessment.get("triage_level", "URGENT")
    css = f"level-{level.lower()}"
    color = TRIAGE_COLORS.get(level, "🟠")

    st.markdown(f'<div class="{css}"><h2>{color} {t(level)}</h2><p>{t(assessment.get("assessment",""))}</p></div>', unsafe_allow_html=True)

    st.markdown("### 📍 " + t("Find Nearest Hospitals"))

    c1, c2 = st.columns(2)
    with c1:
        lat = st.number_input(t("Latitude"), value=48.78, format="%.4f")
    with c2:
        lon = st.number_input(t("Longitude"), value=9.18, format="%.4f")
    st.caption(t("💡 In production, GPS is automatic."))

    col1, col2 = st.columns(2)
    with col1:
        if st.button(t("🔍 Find Hospitals"), type="primary", use_container_width=True, key="find_h"):
            with st.spinner(t("Searching...")):
                hospitals = maps_handler.find_nearest_hospitals(lat, lon, count=3)
                st.session_state.nearby_hospitals = hospitals
                st.session_state.patient_lat = lat
                st.session_state.patient_lon = lon
                st.rerun()
    with col2:
        if st.button(t("⏭ Skip"), use_container_width=True, key="skip_loc"):
            _notify_hospital(None, None, None, None)
            st.session_state.step = "result"
            st.rerun()

    hospitals = st.session_state.nearby_hospitals
    if hospitals:
        st.markdown("---")
        st.markdown("### 🏥 " + t("Nearest Emergency Hospitals"))
        for i, h in enumerate(hospitals):
            is_best = i == 0
            card_cls = "hospital-card hospital-best" if is_best else "hospital-card"
            badge = " ⭐ FASTEST" if is_best else ""
            st.markdown(
                f'<div class="{card_cls}">'
                f'<strong>#{i+1} {h["name"]}{badge}</strong><br>'
                f'📏 {h["distance_km"]} km · ⏱ {h["eta_minutes"]} min<br>'
                f'<span style="color:#666;font-size:0.85rem">📍 {h.get("address","")}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
            if st.button(f"✅ {t('Go to')} {h['name']}", key=f"sel_h{i}", use_container_width=True):
                st.session_state.selected_hospital = h
                st.session_state.eta_info = {
                    "hospital_name": h["name"], "hospital_lat": h["lat"],
                    "hospital_lon": h["lon"], "eta_minutes": h["eta_minutes"],
                    "distance_km": h["distance_km"], "address": h.get("address", ""),
                    "route_summary": h.get("route_summary", ""),
                    "traffic_delay_minutes": h.get("traffic_delay_minutes", 0),
                }
                _notify_hospital(
                    st.session_state.get("patient_lat"),
                    st.session_state.get("patient_lon"),
                    st.session_state.eta_info, h["name"],
                )
                st.session_state.step = "result"
                st.rerun()


def _notify_hospital(lat, lon, eta, hospital_name):
    location = {"lat": lat, "lon": lon} if lat and lon else None
    eta_min = eta.get("eta_minutes") if eta else None
    record = triage_engine.create_patient_record(
        chief_complaint=st.session_state.complaint_english,
        assessment=st.session_state.assessment,
        language=st.session_state.detected_language,
        eta_minutes=eta_min, location=location,
    )
    if hospital_name:
        record["destination_hospital"] = hospital_name
    hospital_queue.add_patient(record)
    st.session_state.patient_record = record


# ---------------------------------------------------------------------------
# STEP 4: Result
# ---------------------------------------------------------------------------
def render_result():
    assessment = st.session_state.assessment
    record = st.session_state.patient_record
    eta = st.session_state.eta_info
    level = assessment.get("triage_level", "URGENT")
    color = TRIAGE_COLORS.get(level, "🟠")
    css = f"level-{level.lower()}"

    st.markdown(f'<div class="{css}"><h2>{color} {t(level)}</h2><p style="font-size:1.1rem">{t(assessment.get("assessment",""))}</p></div>', unsafe_allow_html=True)

    # Action
    st.markdown(f'<div class="card"><strong>📋 {t("Recommended Action")}</strong><br>{t(assessment.get("recommended_action",""))}<br><br>⏱ <strong>{t("Time")}:</strong> {t(assessment.get("time_sensitivity",""))}</div>', unsafe_allow_html=True)

    # Red flags
    flags = assessment.get("red_flags", [])
    if flags and flags != ["none_identified"]:
        flags_html = "".join(f"<span style='display:inline-block;background:#fef2f2;color:#dc2626;padding:4px 12px;border-radius:8px;margin:3px;font-weight:600'>🚩 {f.replace('_',' ').title()}</span>" for f in flags)
        st.markdown(f'<div class="card"><strong>⚠️ {t("Red Flags")}</strong><br><br>{flags_html}</div>', unsafe_allow_html=True)

    # Risk
    risk = assessment.get("risk_score", 5)
    st.markdown(f"**{t('Risk Score')}:** {risk}/10")
    st.progress(risk / 10)

    # Hospital / ETA
    if eta:
        st.markdown(
            f'<div class="eta-box">'
            f'<strong>🏥 {eta.get("hospital_name","Hospital")}</strong><br>'
            f'📍 {eta.get("address","")}<br>'
            f'📏 {eta.get("distance_km","?")} km · ⏱ {eta.get("eta_minutes","?")} min'
            f'</div>',
            unsafe_allow_html=True,
        )

    if record:
        st.success(f"✅ {t('Hospital notified!')} ID: **{record.get('patient_id','')}**")

    if level == TRIAGE_EMERGENCY:
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
        with st.expander(t("📋 Sources")):
            for s in sources:
                st.markdown(f"- {s}")

    # Answer summary
    if st.session_state.answers:
        with st.expander(t("📝 Your Answers")):
            for i, a in enumerate(st.session_state.answers, 1):
                st.markdown(f"**Q{i}:** {t(a.get('question',''))} → **{a.get('original_answer', a.get('answer',''))}**")

    st.markdown("---")
    if st.button(t("🔄 New Triage"), type="primary", use_container_width=True, key="restart"):
        reset()
        st.rerun()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    step = st.session_state.step
    {"input": render_input, "questions": render_questions,
     "location": render_location, "result": render_result}.get(step, render_input)()

    with st.sidebar:
        st.markdown("### 🏥 CodeZero")
        st.markdown("AI-powered pre-hospital triage system.")
        st.markdown("---")
        st.markdown("**Azure AI Services:**")
        for s in ["OpenAI (GPT-4)", "AI Search (RAG)", "Speech Services", "Translator", "Maps", "Content Safety"]:
            st.markdown(f"- {s}")
        st.markdown("---")
        st.caption("⚠️ Demo only. Call 112/911 for real emergencies.")

if __name__ == "__main__":
    main()