"""
CodeZero Patient App — v2.0
============================
Scenario flow:
  1. INPUT        — Voice (mic) or text. Minimal UI. GPS auto-detected.
  2. PHOTOS       — Optional 1–3 photos (add / delete / re-add)
  3. DEMOGRAPHICS — Age range + sex (2 quick questions)
  4. QUESTIONS    — AI follow-up questions + health number + data sharing consent
  5. TRIAGE       — Emergency call button (112/999/112) OR nearest 3 hospitals
                    with distance, ETA, occupancy
  6. RESULT       — DO / DON'T list, registration number, location tracking note

Hospital dashboard receives:
  - Transcript, photos flag, Q&A, AI assessment, demographics, health record link
"""
from __future__ import annotations
import hashlib
import logging
import os
import random
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.hospital_queue import HospitalQueue
from src.knowledge_indexer import KnowledgeIndexer
from src.maps_handler import MapsHandler
from src.triage_engine import (
    DEMOGRAPHIC_QUESTIONS,
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

RTL_LOCALES = {"ar-SA", "ar-EG", "ar-AE", "he-IL", "fa-IR", "ur-PK"}

# Emergency numbers by detected country (from phone locale / GPS)
EMERGENCY_NUMBERS: dict[str, dict] = {
    "de": {"number": "112", "label": "Notruf"},
    "en-GB": {"number": "999", "label": "Emergency"},
    "tr": {"number": "112", "label": "Acil"},
    "en": {"number": "112", "label": "Emergency"},
    "fr": {"number": "15", "label": "SAMU"},
    "nl": {"number": "112", "label": "Spoed"},
    "default": {"number": "112", "label": "Emergency"},
}

# Simulated ER occupancy (in production: real-time hospital API)
_SIMULATED_OCCUPANCY = ["🟢 Low", "🟡 Moderate", "🟠 High", "🔴 Full"]

def _sim_occupancy(hospital_name: str) -> str:
    # Deterministic but varied per hospital name
    h = int(hashlib.md5(hospital_name.encode()).hexdigest()[:4], 16) % 4
    return _SIMULATED_OCCUPANCY[h]

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="CodeZero", page_icon="🚑", layout="centered")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
* { font-family: 'Inter', sans-serif; }

.block-container { max-width: 500px; padding: 1rem 1rem 4rem 1rem !important; }

/* Big tap-friendly buttons */
.stButton > button {
    min-height: 60px !important; font-size: 1.15rem !important;
    font-weight: 700 !important; border-radius: 14px !important;
    letter-spacing: 0.01em; transition: transform 0.1s;
}
.stButton > button:active { transform: scale(0.97); }

/* Radio — pill style */
div[data-testid="stRadio"] > div { gap: 8px !important; flex-direction: column !important; }
div[data-testid="stRadio"] > div > label {
    font-size: 1.15rem !important; padding: 16px 20px !important;
    border: 2px solid #334155 !important; border-radius: 12px !important;
    min-height: 56px !important; cursor: pointer !important;
    width: 100% !important; display: flex !important; align-items: center !important;
    color: #f1f5f9 !important;
}
div[data-testid="stRadio"] > div > label:hover { border-color: #3b82f6 !important; background: rgba(59,130,246,0.1) !important; }
div[data-testid="stRadio"] > div > label:has(input:checked) { border-color: #3b82f6 !important; background: rgba(59,130,246,0.15) !important; }

/* Text area */
textarea { font-size: 1.1rem !important; border-radius: 12px !important; }

/* Progress bar */
div[data-testid="stProgress"] > div > div { background: #3b82f6 !important; }

/* Audio input */
div[data-testid="stAudioInput"] { margin: 0.5rem 0; }

/* Input fields */
input[type="text"], input[type="number"] { font-size: 1rem !important; }

/* Hospital card */
.hosp-card {
    border: 2px solid #1e293b; border-radius: 14px;
    padding: 1rem 1.1rem; margin-bottom: 0.6rem;
    background: #0f172a; transition: border-color 0.15s;
}
.hosp-card.fastest { border-color: #22c55e; background: #052e16; }
.hosp-card.second  { border-color: #1e293b; }

/* DO/DON'T list */
.do-item   { color: #4ade80; font-size: 1rem; padding: 4px 0; }
.dont-item { color: #f87171; font-size: 1rem; padding: 4px 0; }

/* Registration number box */
.reg-box {
    background: #0f172a; border: 2px solid #3b82f6;
    border-radius: 12px; padding: 0.8rem 1rem; text-align: center;
    font-size: 1.8rem; font-weight: 800; letter-spacing: 0.15em; color: #60a5fa;
    margin: 0.8rem 0;
}

/* Photo grid */
.photo-row { display: flex; gap: 0.5rem; flex-wrap: wrap; margin: 0.5rem 0; }
</style>
""", unsafe_allow_html=True)


# ── Services ──────────────────────────────────────────────────────────────────
@st.cache_resource
def load_services():
    status = {}
    ki = te = tr = mh = hq = sh = None
    try:
        ki = KnowledgeIndexer(); status["AI Search"] = ki._initialized
    except Exception: status["AI Search"] = False
    try:
        tr = Translator(); status["Translator"] = tr._initialized
    except Exception: status["Translator"] = False
    try:
        te = TriageEngine(knowledge_indexer=ki, translator=tr)
        status["GPT-4"] = te._initialized
    except Exception: status["GPT-4"] = False
    try:
        mh = MapsHandler(); status["Azure Maps"] = mh._initialized
    except Exception: status["Azure Maps"] = False
    try:
        hq = HospitalQueue(); status["Queue"] = True
    except Exception: status["Queue"] = False
    try:
        sh = SpeechHandler() if _HAS_SPEECH else None
        status["Speech"] = bool(sh and sh._initialized)
    except Exception: status["Speech"] = False
    return te, tr, mh, hq, sh, status

triage_engine, translator, maps_handler, hospital_queue, speech_handler, _svc_status = load_services()

# ── Session state ─────────────────────────────────────────────────────────────
_DEFAULTS: dict = dict(
    step="input",
    complaint_text="",
    complaint_english="",
    detected_language="en-US",
    photos=[],              # list of bytes — max 3
    questions=[],
    answers=[],
    q_idx=0,
    demographics={},
    demo_idx=0,
    health_number="",       # patient-entered health number
    data_consent=False,     # consent to share with hospital
    assessment=None,
    patient_record=None,
    eta_info=None,
    nearby_hospitals=[],
    selected_hospital=None,
    patient_lat=None,
    patient_lon=None,
    gps_fetched=False,
    pre_arrival_advice=None,
    reg_number=None,        # registration number shown on arrival
    country="DE",           # detected from GPS or language
)
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

_TC = "_tcache"
if _TC not in st.session_state:
    st.session_state[_TC] = {}


# ── Helpers ───────────────────────────────────────────────────────────────────
def t(text: str) -> str:
    lang = st.session_state.detected_language
    if not translator or lang.startswith("en"):
        return text
    cache = st.session_state[_TC]
    key = f"{lang}:{text[:80]}"
    if key in cache:
        return cache[key]
    try:
        out = translator.translate_from_english(text, lang)
        cache[key] = out
        return out
    except Exception:
        return text


def reset():
    for k, v in _DEFAULTS.items():
        st.session_state[k] = v
    st.session_state[_TC] = {}


def _inject_rtl():
    if st.session_state.detected_language in RTL_LOCALES:
        st.markdown('<style>.block-container { direction: rtl; text-align: right; }</style>', unsafe_allow_html=True)


def _emergency_number() -> dict:
    lang = st.session_state.detected_language.split("-")[0]
    ctry = st.session_state.get("country", "DE")
    if ctry == "UK":
        return {"number": "999", "label": "Emergency"}
    return EMERGENCY_NUMBERS.get(lang, EMERGENCY_NUMBERS["default"])


def _gen_reg_number() -> str:
    return "CZ-" + datetime.now(timezone.utc).strftime("%H%M") + "-" + str(random.randint(1000, 9999))


def _try_transcribe(audio) -> str | None:
    if not speech_handler or not getattr(speech_handler, "_initialized", False):
        return None
    raw = audio.getvalue()
    if not raw:
        return None
    try:
        is_wav  = raw[:4] == b"RIFF"
        is_ogg  = raw[:4] == b"OggS"
        if is_wav:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp.write(raw); wav_path = tmp.name
        else:
            src = ".ogg" if is_ogg else ".webm"
            wav_path = speech_handler.convert_browser_audio_to_wav(raw, source_suffix=src)
            if not wav_path:
                return None
        result = speech_handler.recognize_from_audio_file(wav_path)
        try:
            os.unlink(wav_path)
        except OSError:
            pass
        if result and result.get("text"):
            st.session_state.detected_language = result.get("language", "en-US")
            return result["text"]
    except Exception as exc:
        logger.error("Transcription error: %s", exc)
    return None


def _detect_country_from_gps(lat: float, lon: float) -> str:
    """Rough country detection from lat/lon bounding boxes."""
    if 47.2 <= lat <= 55.1 and 5.9 <= lon <= 15.1:
        return "DE"
    if 49.9 <= lat <= 60.9 and -8.6 <= lon <= 1.8:
        return "UK"
    if 35.8 <= lat <= 42.1 and 26.0 <= lon <= 44.8:
        return "TR"
    return "DE"


def _do_process(text: str) -> None:
    detected_code: str | None = None
    if translator:
        try:
            detected_code = translator.detect_language(text)
        except Exception:
            pass
    locale_map = {
        "de": "de-DE", "tr": "tr-TR", "ar": "ar-SA", "fr": "fr-FR",
        "es": "es-ES", "it": "it-IT", "ru": "ru-RU", "en": "en-US",
        "nl": "nl-NL", "pl": "pl-PL",
    }
    st.session_state.detected_language = locale_map.get(detected_code or "en", "en-US")
    st.session_state[_TC] = {}

    english = text
    if translator:
        try:
            english = translator.translate_to_english(text, st.session_state.detected_language)
        except Exception:
            pass

    st.session_state.complaint_text    = text
    st.session_state.complaint_english = english
    st.session_state.demographics      = {}
    st.session_state.demo_idx          = 0
    st.session_state.q_idx             = 0
    st.session_state.answers           = []
    st.session_state.questions         = []
    st.session_state.step              = "photos"
    st.rerun()


def _do_notify(lat, lon, eta, hospital_name):
    location = {"lat": lat, "lon": lon} if lat and lon else None
    eta_min  = eta.get("eta_minutes") if eta else None

    # Build photos metadata list
    photos_meta = []
    for i, photo_bytes in enumerate(st.session_state.photos):
        photos_meta.append({"index": i + 1, "size_bytes": len(photo_bytes)})

    if triage_engine:
        record = triage_engine.create_patient_record(
            chief_complaint=st.session_state.complaint_english,
            assessment=st.session_state.assessment,
            language=st.session_state.detected_language,
            eta_minutes=eta_min,
            location=location,
            demographics=st.session_state.get("demographics"),
        )
    else:
        record = {
            "patient_id": "DEMO-" + str(random.randint(1000, 9999)),
            "triage_level": TRIAGE_URGENT,
            "chief_complaint": st.session_state.complaint_text,
            "language": st.session_state.detected_language,
        }

    if hospital_name:
        record["destination_hospital"] = hospital_name

    # Enrich record
    record["qa_transcript"]   = st.session_state.answers
    record["complaint_text"]  = st.session_state.complaint_text   # original language
    record["has_photo"]       = len(st.session_state.photos) > 0
    record["photo_count"]     = len(st.session_state.photos)
    record["photos_meta"]     = photos_meta
    record["photo_note"]      = f"Patient attached {len(st.session_state.photos)} photo(s)" if st.session_state.photos else ""
    record["health_number"]   = st.session_state.get("health_number", "")
    record["data_consent"]    = st.session_state.get("data_consent", False)
    record["age_range"]       = st.session_state.demographics.get("age_range", "—")
    record["sex"]             = st.session_state.demographics.get("sex", "—")

    if hospital_queue:
        hospital_queue.add_patient(record)

    reg = _gen_reg_number()
    st.session_state.patient_record = record
    st.session_state.reg_number     = reg

    # Pre-arrival advice
    if triage_engine:
        try:
            advice = triage_engine.generate_pre_arrival_advice(
                chief_complaint=st.session_state.complaint_english,
                assessment=st.session_state.assessment,
                language=st.session_state.detected_language,
            )
            st.session_state.pre_arrival_advice = advice
        except Exception as exc:
            logger.error("Pre-arrival advice: %s", exc)
            st.session_state.pre_arrival_advice = None


# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — INPUT
# Ultra-minimal: voice first, tiny "type instead" option
# ══════════════════════════════════════════════════════════════════════════════
def page_input() -> None:
    _inject_rtl()

    # GPS detection
    if not st.session_state.gps_fetched:
        try:
            p = st.query_params
            if "cz_lat" in p and "cz_lon" in p:
                lat = float(p["cz_lat"]); lon = float(p["cz_lon"])
                st.session_state.patient_lat = lat
                st.session_state.patient_lon = lon
                st.session_state.gps_fetched = True
                st.session_state.country = _detect_country_from_gps(lat, lon)
        except Exception:
            pass

    if not st.session_state.gps_fetched:
        st.components.v1.html("""
<script>
(function(){
  if(!navigator.geolocation)return;
  navigator.geolocation.getCurrentPosition(function(p){
    try{
      var u=new URL(window.parent.location.href);
      u.searchParams.set("cz_lat",p.coords.latitude.toFixed(6));
      u.searchParams.set("cz_lon",p.coords.longitude.toFixed(6));
      window.parent.location.replace(u.toString());
    }catch(e){}
  },function(){},{timeout:8000,enableHighAccuracy:false});
})();
</script>""", height=0)

    # ── Header ──
    st.markdown("""
<div style="text-align:center; padding:2rem 0 1rem 0;">
  <div style="font-size:4rem; line-height:1.1;">🚑</div>
  <h1 style="font-size:2.2rem; font-weight:900; margin:0.2rem 0 0.4rem 0; color:#f8fafc;">CodeZero</h1>
  <p style="font-size:1.05rem; color:#64748b; margin:0;">Medical emergency assistant</p>
</div>
""", unsafe_allow_html=True)

    # GPS status
    if st.session_state.patient_lat:
        st.markdown('<p style="text-align:center;font-size:0.88rem;color:#22c55e;margin:0 0 0.8rem 0;">📍 Location detected</p>', unsafe_allow_html=True)
    else:
        st.markdown('<p style="text-align:center;font-size:0.88rem;color:#475569;margin:0 0 0.8rem 0;">📍 Allow location access when prompted</p>', unsafe_allow_html=True)

    # ── Primary: voice ──
    st.markdown("""
<div style="text-align:center; margin:0.5rem 0 0.2rem 0;">
  <p style="font-size:1.25rem; font-weight:700; color:#f1f5f9; margin:0 0 0.2rem 0;">🎤 Record your symptoms</p>
  <p style="font-size:0.95rem; color:#64748b; margin:0;">Speak in your language — tap the microphone</p>
</div>
""", unsafe_allow_html=True)

    if hasattr(st, "audio_input"):
        audio = st.audio_input(" ", label_visibility="collapsed", key="audio_main")
        if audio is not None:
            with st.spinner("🔄 Processing..."):
                transcribed = _try_transcribe(audio)
            if transcribed:
                st.markdown(f"""
<div style="background:#052e16; border:2px solid #22c55e; border-radius:12px; padding:1rem 1.1rem; margin:0.6rem 0;">
  <p style="color:#86efac; font-size:0.8rem; margin:0 0 0.3rem 0; text-transform:uppercase; letter-spacing:0.05em;">Understood</p>
  <p style="color:#f0fdf4; font-size:1.05rem; margin:0; font-style:italic;">"{transcribed}"</p>
</div>
""", unsafe_allow_html=True)
                if st.button("Continue →", type="primary", use_container_width=True, key="btn_voice"):
                    _do_process(transcribed)
            else:
                st.markdown('<p style="color:#f87171;text-align:center;font-size:0.95rem;margin:0.4rem 0;">Could not process audio — please type below</p>', unsafe_allow_html=True)
    else:
        st.info("Upgrade Streamlit for voice input: `pip install -U streamlit`")

    # ── "Or type" — minimal, secondary ──
    with st.expander("✏️ Type instead", expanded=False):
        complaint = st.text_area(
            "Describe your symptoms",
            placeholder="e.g. Sudden chest pain, difficulty breathing...",
            height=90,
            label_visibility="collapsed",
        )
        st.caption("🌍 Any language is understood")
        if st.button("Continue →", type="primary", use_container_width=True, key="btn_text"):
            if complaint and complaint.strip():
                _do_process(complaint.strip())
            else:
                st.warning("Please describe your symptoms first.")


# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — PHOTOS (optional, max 3)
# ══════════════════════════════════════════════════════════════════════════════
def page_photos() -> None:
    _inject_rtl()

    st.markdown("""
<div style="text-align:center; padding:1rem 0 0.5rem 0;">
  <p style="font-size:1.3rem; font-weight:700; color:#f1f5f9; margin:0;">📷 Add photos</p>
  <p style="font-size:0.95rem; color:#64748b; margin:0.2rem 0 0;">Wound, rash, swelling — up to 3 photos</p>
</div>
""", unsafe_allow_html=True)

    photos = st.session_state.photos
    max_photos = 3

    # Show existing photos with delete option
    if photos:
        cols = st.columns(min(len(photos), 3))
        for i, photo_bytes in enumerate(photos):
            with cols[i % 3]:
                st.image(photo_bytes, use_container_width=True, caption=f"Photo {i+1}")
                if st.button("🗑 Remove", key=f"del_photo_{i}", use_container_width=True):
                    st.session_state.photos.pop(i)
                    st.rerun()

    # Add more photos
    if len(photos) < max_photos:
        st.markdown(f'<p style="color:#64748b;font-size:0.9rem;margin:0.3rem 0;">({len(photos)}/{max_photos} photos)</p>', unsafe_allow_html=True)

        # Camera input
        try:
            if hasattr(st, "camera_input"):
                new_photo = st.camera_input("Take a photo", label_visibility="collapsed", key=f"cam_{len(photos)}")
                if new_photo is not None:
                    st.session_state.photos.append(new_photo.getvalue())
                    st.rerun()
        except Exception:
            pass

        # File upload fallback
        uploaded = st.file_uploader(
            "Or upload a photo",
            type=["jpg", "jpeg", "png", "heic"],
            label_visibility="collapsed",
            key=f"up_{len(photos)}",
        )
        if uploaded is not None:
            st.session_state.photos.append(uploaded.getvalue())
            st.rerun()

    # Navigation
    col_skip, col_cont = st.columns(2)
    with col_skip:
        if st.button("Skip →", use_container_width=True, key="skip_photos"):
            st.session_state.step = "demographics"
            st.rerun()
    with col_cont:
        label = "Continue →" if photos else "Skip →"
        if st.button(label, type="primary", use_container_width=True, key="cont_photos"):
            st.session_state.step = "demographics"
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — DEMOGRAPHICS (age + sex)
# ══════════════════════════════════════════════════════════════════════════════
def page_demographics() -> None:
    _inject_rtl()

    dqs  = DEMOGRAPHIC_QUESTIONS
    idx  = st.session_state.demo_idx

    if idx >= len(dqs):
        # Generate AI questions
        with st.spinner("Preparing your assessment..."):
            if triage_engine:
                st.session_state.questions = triage_engine.generate_questions(
                    st.session_state.complaint_english,
                    demographics=st.session_state.demographics,
                )
            else:
                st.session_state.questions = []
        st.session_state.q_idx = 0
        st.session_state.step  = "questions"
        st.rerun()
        return

    st.markdown(f"""
<div style="text-align:center;padding:0.8rem 0 0.3rem;">
  <p style="font-size:1.2rem;font-weight:700;color:#f1f5f9;margin:0;">Quick questions first</p>
  <p style="font-size:0.9rem;color:#64748b;margin:0.1rem 0;">{idx+1} of {len(dqs)}</p>
</div>""", unsafe_allow_html=True)

    st.progress((idx) / len(dqs))

    q = dqs[idx]
    st.markdown(f'<p style="font-size:1.15rem;font-weight:600;color:#f1f5f9;margin:0.8rem 0 0.5rem 0;">{t(q["question"])}</p>', unsafe_allow_html=True)

    answer = st.radio("Select", [t(o) for o in q["options"]], key=f"demo_{idx}", label_visibility="collapsed")

    if st.button("Next →", type="primary", use_container_width=True, key=f"demo_next_{idx}"):
        if answer:
            eng = answer
            if translator:
                try:
                    eng = translator.translate_to_english(answer, st.session_state.detected_language)
                except Exception:
                    pass
            if idx == 0:
                st.session_state.demographics["age_range"] = eng
            elif idx == 1:
                st.session_state.demographics["sex"] = eng
            st.session_state.demo_idx += 1
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 — QUESTIONS + health number + consent
# ══════════════════════════════════════════════════════════════════════════════
def page_questions() -> None:
    _inject_rtl()

    questions = st.session_state.questions
    idx       = st.session_state.q_idx
    lang      = st.session_state.detected_language

    # After all AI questions: health number + consent screen
    if idx >= len(questions):
        _page_consent()
        return

    total = len(questions) + 1  # +1 for consent screen
    st.progress(idx / total)
    st.markdown(f'<p style="color:#64748b;font-size:0.8rem;text-align:right;margin:0 0 0.5rem 0;">Question {idx+1} of {len(questions)}</p>', unsafe_allow_html=True)

    question = questions[idx]
    q_text: str  = question.get("question", "")
    q_type: str  = question.get("type", "yes_no")
    options: list = question.get("options", [])

    # Normalise free-text / empty options
    if q_type == "free_text" or not options:
        q_lower = q_text.lower()
        if any(w in q_lower for w in ["when","how long","since","start","began","zaman","başla"]):
            q_type = "multiple_choice"
            options = ["Just now","< 1 hour ago","1–6 hours ago","6–24 hours ago","More than 1 day"]
        elif any(w in q_lower for w in ["how","rate","scale","severity","şiddet","puan","pain"]):
            q_type = "scale"
            options = [str(i) for i in range(1, 11)]
        elif any(w in q_lower for w in ["where","location","nerede","yer"]):
            q_type = "multiple_choice"
            options = ["Head/neck","Chest","Abdomen","Back","Arms","Legs","Whole body"]
        else:
            q_type = "yes_no"
            options = ["Yes","No","Not sure"]

    st.markdown(f'<p style="font-size:1.15rem;font-weight:600;color:#f1f5f9;margin:0 0 0.5rem 0;">{t(q_text)}</p>', unsafe_allow_html=True)

    answer = None
    if q_type == "scale":
        answer = st.select_slider("", options=options, key=f"q_{idx}")
    elif q_type == "multiple_choice":
        sel = st.multiselect("", [t(o) for o in options], key=f"q_{idx}", label_visibility="collapsed")
        answer = ", ".join(sel) if sel else None
    else:
        answer = st.radio("", [t(o) for o in options], key=f"q_{idx}", label_visibility="collapsed")

    c1, c2 = st.columns(2)
    with c1:
        if idx > 0 and st.button("← Back", use_container_width=True, key="q_back"):
            st.session_state.q_idx -= 1
            if st.session_state.answers: st.session_state.answers.pop()
            st.rerun()
    with c2:
        if st.button("Next →", type="primary", use_container_width=True, key="q_next"):
            if answer:
                eng = str(answer)
                if translator:
                    try: eng = translator.translate_to_english(str(answer), lang)
                    except Exception: pass
                st.session_state.answers.append({"question": q_text, "answer": eng, "original_answer": str(answer)})
                st.session_state.q_idx += 1
                st.rerun()
            else:
                st.warning("Please select an answer.")


def _page_consent() -> None:
    """Health number + data sharing consent — last step before triage."""
    _inject_rtl()

    st.markdown("""
<div style="text-align:center;padding:0.5rem 0 0.8rem;">
  <p style="font-size:1.2rem;font-weight:700;color:#f1f5f9;margin:0;">Almost done</p>
  <p style="font-size:0.9rem;color:#64748b;margin:0.1rem 0;">One last step before your assessment</p>
</div>""", unsafe_allow_html=True)

    # Health number (optional)
    st.markdown('<p style="font-size:1rem;font-weight:600;color:#cbd5e1;margin:0 0 0.3rem 0;">🪪 Your health / insurance number <span style="color:#475569;font-weight:400;">(optional)</span></p>', unsafe_allow_html=True)
    hn = st.text_input(
        "Health number",
        value=st.session_state.health_number,
        placeholder="e.g. DE-1985-447291 / NHS-789012345 / SGK-5512873690",
        label_visibility="collapsed",
    )
    st.session_state.health_number = hn
    if hn:
        st.markdown('<p style="color:#4ade80;font-size:0.85rem;margin:0;">✅ Health number entered — your records will be available to the treating team</p>', unsafe_allow_html=True)

    st.divider()

    # Consent
    st.markdown('<p style="font-size:1rem;font-weight:600;color:#cbd5e1;margin:0 0 0.5rem 0;">📋 Data sharing consent</p>', unsafe_allow_html=True)
    st.markdown('<p style="font-size:0.92rem;color:#94a3b8;margin:0 0 0.8rem 0;">Do you consent to sharing the information you have provided — including your symptoms, answers, and health number — with the hospital you are directed to?</p>', unsafe_allow_html=True)

    consent = st.radio(
        "Consent",
        ["✅ Yes — share my information with the hospital", "❌ No — do not share my data"],
        label_visibility="collapsed",
        key="consent_radio",
    )
    st.session_state.data_consent = "Yes" in consent

    if st.button("Get my assessment →", type="primary", use_container_width=True, key="btn_consent"):
        # Run triage assessment
        with st.spinner("🔍 Analysing your answers..."):
            if triage_engine:
                assessment = triage_engine.assess_triage(
                    st.session_state.complaint_english,
                    st.session_state.answers,
                )
            else:
                assessment = {
                    "triage_level": TRIAGE_URGENT,
                    "assessment": "AI not configured — demo mode.",
                    "red_flags": [], "risk_score": 5,
                    "recommended_action": "Please see a doctor.",
                    "time_sensitivity": "Soon",
                    "source_guidelines": [], "suspected_conditions": [],
                }
        st.session_state.assessment = assessment
        st.session_state.step = "triage"
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# STEP 5 — TRIAGE (emergency number + hospital selection)
# ══════════════════════════════════════════════════════════════════════════════
def page_triage() -> None:
    _inject_rtl()

    assessment = st.session_state.assessment
    level      = assessment.get("triage_level", TRIAGE_URGENT)
    emg        = _emergency_number()

    # ── Emergency banner ──────────────────────────────────────────────────
    if level == TRIAGE_EMERGENCY:
        st.markdown(f"""
<div style="background:#7f1d1d;border-left:5px solid #dc2626;border-radius:14px;padding:1.1rem 1.3rem;margin:0.2rem 0 1rem 0;">
  <p style="font-size:1.4rem;font-weight:800;color:#fef2f2;margin:0 0 0.2rem 0;">🚨 Go to emergency immediately</p>
  <p style="font-size:1rem;color:#fecaca;margin:0;">Your symptoms require urgent care — do not wait</p>
</div>
""", unsafe_allow_html=True)
        # Big call button
        st.markdown(f"""
<div style="text-align:center;margin:0.5rem 0 1rem 0;">
  <a href="tel:{emg['number']}" style="background:#dc2626;color:white;padding:20px 48px;
     border-radius:14px;font-size:1.6rem;font-weight:800;text-decoration:none;
     display:inline-block;box-shadow:0 4px 16px rgba(220,38,38,0.4);">
    📞 CALL {emg['number']}
  </a>
  <p style="color:#64748b;font-size:0.85rem;margin:0.5rem 0 0 0;">{emg['label']} · Tap to call</p>
</div>
<div style="text-align:center;margin:0 0 0.8rem 0;">
  <p style="color:#94a3b8;font-size:0.9rem;">— or select a hospital below —</p>
</div>
""", unsafe_allow_html=True)

    elif level == TRIAGE_URGENT:
        st.markdown("""
<div style="background:#78350f;border-left:5px solid #f59e0b;border-radius:14px;padding:1.1rem 1.3rem;margin:0.2rem 0 1rem 0;">
  <p style="font-size:1.25rem;font-weight:800;color:#fefce8;margin:0 0 0.2rem 0;">⚠️ You need to go to hospital soon</p>
  <p style="font-size:0.95rem;color:#fde68a;margin:0;">Please find a hospital within the next 30 minutes</p>
</div>
""", unsafe_allow_html=True)
    else:
        st.markdown("""
<div style="background:#14532d;border-left:5px solid #22c55e;border-radius:14px;padding:1.1rem 1.3rem;margin:0.2rem 0 1rem 0;">
  <p style="font-size:1.2rem;font-weight:700;color:#f0fdf4;margin:0 0 0.2rem 0;">ℹ️ You should see a doctor today</p>
  <p style="font-size:0.9rem;color:#bbf7d0;margin:0;">Your symptoms are not immediately life-threatening</p>
</div>
""", unsafe_allow_html=True)

    # ── Hospital search ────────────────────────────────────────────────────
    st.markdown('<p style="font-size:1.1rem;font-weight:700;color:#f1f5f9;margin:0.5rem 0 0.3rem 0;">🏥 Nearest Emergency Hospitals</p>', unsafe_allow_html=True)

    lat = st.session_state.patient_lat
    lon = st.session_state.patient_lon
    country = st.session_state.get("country", "DE")

    # Auto-search on first render
    if not st.session_state.nearby_hospitals:
        if lat and lon and maps_handler:
            with st.spinner("Finding nearest hospitals..."):
                hospitals = maps_handler.find_nearest_hospitals(lat, lon, count=3, country=country)
                st.session_state.nearby_hospitals = hospitals
            st.rerun()
        elif not lat:
            # Manual coordinate entry
            st.caption("📍 GPS not available — enter approximate location")
            c1, c2 = st.columns(2)
            with c1:
                lat = st.number_input("Latitude", value=48.78, format="%.4f", key="manual_lat")
            with c2:
                lon = st.number_input("Longitude", value=9.18, format="%.4f", key="manual_lon")
            if st.button("Find Hospitals", type="primary", use_container_width=True, key="find_manual"):
                if maps_handler:
                    hospitals = maps_handler.find_nearest_hospitals(lat, lon, count=3, country=country)
                    st.session_state.nearby_hospitals = hospitals
                    st.session_state.patient_lat = lat
                    st.session_state.patient_lon = lon
                    st.rerun()

    hospitals = st.session_state.nearby_hospitals

    if hospitals:
        for i, h in enumerate(hospitals):
            occupancy = _sim_occupancy(h["name"])
            occ_color = {"🟢": "#22c55e","🟡": "#eab308","🟠": "#f97316","🔴": "#ef4444"}.get(occupancy[:2], "#94a3b8")
            is_fastest = i == 0
            card_class = "fastest" if is_fastest else "second"
            rank_badge = "⭐ FASTEST" if is_fastest else f"#{i+1}"

            st.markdown(f"""
<div class="hosp-card {card_class}">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:0.4rem;">
    <span style="font-size:1rem;font-weight:700;color:#f8fafc;">{rank_badge} {h['name']}</span>
  </div>
  <div style="display:flex;gap:1rem;flex-wrap:wrap;margin-bottom:0.4rem;">
    <span style="color:#94a3b8;font-size:0.95rem;">📏 {h['distance_km']} km</span>
    <span style="color:#94a3b8;font-size:0.95rem;">⏱ ~{h['eta_minutes']} min</span>
    <span style="color:{occ_color};font-size:0.9rem;font-weight:600;">{occupancy}</span>
  </div>
  <p style="color:#64748b;font-size:0.88rem;margin:0;">📍 {h.get('address','')}</p>
</div>
""", unsafe_allow_html=True)

            if st.button(f"Go to {h['name']}", key=f"sel_{i}", use_container_width=True,
                         type="primary" if is_fastest else "secondary"):
                eta_info = {
                    "hospital_name": h["name"],
                    "hospital_lat":  h["lat"],
                    "hospital_lon":  h["lon"],
                    "eta_minutes":   h["eta_minutes"],
                    "distance_km":   h["distance_km"],
                    "address":       h.get("address", ""),
                    "route_summary": h.get("route_summary", ""),
                    "occupancy":     occupancy,
                }
                st.session_state.selected_hospital = h
                st.session_state.eta_info = eta_info
                _do_notify(st.session_state.patient_lat, st.session_state.patient_lon, eta_info, h["name"])
                st.session_state.step = "result"
                st.rerun()
    else:
        if lat:
            st.info("Searching for hospitals...")


# ══════════════════════════════════════════════════════════════════════════════
# STEP 6 — RESULT (instructions, reg number, tracking note)
# ══════════════════════════════════════════════════════════════════════════════
def page_result() -> None:
    _inject_rtl()

    assessment = st.session_state.assessment or {}
    eta        = st.session_state.eta_info or {}
    record     = st.session_state.patient_record or {}
    level      = assessment.get("triage_level", TRIAGE_URGENT)
    reg_no     = st.session_state.reg_number or _gen_reg_number()
    emg        = _emergency_number()

    # ── Confirmation banner ───────────────────────────────────────────────
    if level == TRIAGE_EMERGENCY:
        st.markdown("""
<div style="background:#7f1d1d;border-left:5px solid #dc2626;border-radius:14px;padding:1.1rem 1.3rem;margin:0.3rem 0 0.8rem 0;">
  <p style="font-size:1.3rem;font-weight:800;color:#fef2f2;margin:0 0 0.2rem 0;">🚨 Hospital notified — head there now!</p>
  <p style="font-size:0.95rem;color:#fecaca;margin:0;">They are preparing for your arrival</p>
</div>""", unsafe_allow_html=True)
    elif level == TRIAGE_URGENT:
        st.markdown("""
<div style="background:#78350f;border-left:5px solid #f59e0b;border-radius:14px;padding:1.1rem 1.3rem;margin:0.3rem 0 0.8rem 0;">
  <p style="font-size:1.2rem;font-weight:800;color:#fefce8;margin:0 0 0.2rem 0;">✅ Hospital notified</p>
  <p style="font-size:0.9rem;color:#fde68a;margin:0;">Please follow the instructions below</p>
</div>""", unsafe_allow_html=True)
    else:
        st.markdown("""
<div style="background:#0c4a6e;border-left:5px solid #0ea5e9;border-radius:14px;padding:1.1rem 1.3rem;margin:0.3rem 0 0.8rem 0;">
  <p style="font-size:1.2rem;font-weight:700;color:#f0f9ff;margin:0 0 0.2rem 0;">✅ Your information has been sent</p>
  <p style="font-size:0.9rem;color:#bae6fd;margin:0;">See instructions below before leaving</p>
</div>""", unsafe_allow_html=True)

    # ── Hospital + ETA ───────────────────────────────────────────────────
    if eta:
        occ = eta.get("occupancy", "")
        st.markdown(f"""
<div style="background:#1e293b;border-radius:12px;padding:0.9rem 1rem;margin:0.3rem 0 0.8rem 0;">
  <p style="font-size:1.05rem;font-weight:700;color:#f1f5f9;margin:0 0 0.3rem 0;">🏥 {eta.get('hospital_name','')}</p>
  <p style="color:#94a3b8;font-size:0.88rem;margin:0 0 0.2rem 0;">📍 {eta.get('address','')}</p>
  <div style="display:flex;gap:1rem;flex-wrap:wrap;">
    <span style="color:#7dd3fc;font-size:0.95rem;">📏 {eta.get('distance_km','?')} km</span>
    <span style="color:#7dd3fc;font-size:0.95rem;">⏱ ~{eta.get('eta_minutes','?')} min</span>
    <span style="color:#86efac;font-size:0.9rem;">{occ}</span>
  </div>
</div>
""", unsafe_allow_html=True)

    # ── Registration number ───────────────────────────────────────────────
    st.markdown('<p style="font-size:0.9rem;font-weight:600;color:#94a3b8;margin:0 0 0.2rem 0;text-transform:uppercase;letter-spacing:0.06em;">Your hospital registration number</p>', unsafe_allow_html=True)
    st.markdown(f'<div class="reg-box">{reg_no}</div>', unsafe_allow_html=True)
    st.markdown('<p style="color:#64748b;font-size:0.82rem;margin:0 0 0.8rem 0;text-align:center;">Show this number at the hospital reception when you arrive</p>', unsafe_allow_html=True)

    # ── Emergency call (for EMERGENCY level) ────────────────────────────
    if level == TRIAGE_EMERGENCY:
        st.markdown(f"""
<div style="text-align:center;margin:0.5rem 0 1rem 0;">
  <a href="tel:{emg['number']}" style="background:#dc2626;color:white;padding:16px 40px;
     border-radius:12px;font-size:1.4rem;font-weight:800;text-decoration:none;
     display:inline-block;">
    📞 CALL {emg['number']}
  </a>
</div>
""", unsafe_allow_html=True)

    # ── Pre-arrival advice ────────────────────────────────────────────────
    advice = st.session_state.pre_arrival_advice
    if advice:
        do_list   = advice.get("do_list",   [])
        dont_list = advice.get("dont_list", [])
        if do_list or dont_list:
            border = {"EMERGENCY": "#dc2626", "URGENT": "#f59e0b", "ROUTINE": "#22c55e"}.get(level, "#3b82f6")
            st.markdown(f'<div style="border:2px solid {border};border-radius:14px;padding:1rem 1.2rem;margin:0.5rem 0;">', unsafe_allow_html=True)
            st.markdown("**⏱ Before you arrive**")
            if do_list:
                st.markdown("**✅ DO:**")
                for item in do_list:
                    st.markdown(f'<p class="do-item">✓ {item}</p>', unsafe_allow_html=True)
            if dont_list:
                st.markdown("**❌ DON'T:**")
                for item in dont_list:
                    st.markdown(f'<p class="dont-item">✗ {item}</p>', unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.info("⏳ Personalised advice being prepared...")

    # ── Location tracking note ─────────────────────────────────────────────
    st.markdown("""
<div style="background:#0f172a;border:1px solid #1e293b;border-radius:12px;padding:0.9rem 1rem;margin:0.8rem 0;">
  <p style="color:#94a3b8;font-size:0.88rem;margin:0;">
    📍 <strong style="color:#cbd5e1;">Keep your location enabled</strong> while travelling to hospital —
    your care team can track your arrival in real time.
  </p>
</div>
""", unsafe_allow_html=True)

    st.divider()
    if st.button("🔄 New assessment", type="primary", use_container_width=True, key="restart"):
        reset(); st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
def render_sidebar() -> None:
    with st.sidebar:
        st.markdown("### 🚑 CodeZero")
        st.caption("AI pre-hospital triage")
        st.divider()
        # Step indicator
        step = st.session_state.step
        steps = ["input","photos","demographics","questions","triage","result"]
        labels = ["Symptoms","Photos","Info","Questions","Hospital","Result"]
        for i, (s, lab) in enumerate(zip(steps, labels)):
            icon = "✅" if steps.index(step) > i else ("▶" if s == step else "○")
            st.markdown(f"{icon} {lab}")
        st.divider()
        # Services
        for svc, ok in _svc_status.items():
            st.markdown(f"{'✅' if ok else '⚠️'} {svc} — *{'Live' if ok else 'Demo'}*")
        st.divider()
        st.caption("⚠️ Demo only. Call 112 for real emergencies.")


# ══════════════════════════════════════════════════════════════════════════════
# ROUTER
# ══════════════════════════════════════════════════════════════════════════════
def main() -> None:
    render_sidebar()
    step = st.session_state.step
    if   step == "photos":       page_photos()
    elif step == "demographics": page_demographics()
    elif step == "questions":    page_questions()
    elif step == "triage":       page_triage()
    elif step == "result":       page_result()
    else:                        page_input()

if __name__ == "__main__":
    main()