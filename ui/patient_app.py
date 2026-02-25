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
/* ── Mobile-first layout ── */
.block-container {
    max-width: 480px;
    padding: 1rem 1rem 4rem 1rem !important;
}

/* ── All buttons: large touch targets ── */
.stButton > button {
    min-height: 72px !important;
    font-size: 1.3rem !important;
    font-weight: 700 !important;
    border-radius: 16px !important;
    letter-spacing: 0.02em;
}

/* ── Radio options: big pill buttons with dark theme contrast ── */
div[data-testid="stRadio"] > div {
    gap: 10px !important;
    flex-direction: column !important;
}
div[data-testid="stRadio"] > div > label {
    font-size: 1.25rem !important;
    padding: 18px 24px !important;
    border: 2.5px solid #475569 !important;
    border-radius: 14px !important;
    min-height: 64px !important;
    cursor: pointer !important;
    width: 100% !important;
    display: flex !important;
    align-items: center !important;
    color: #f1f5f9 !important;
}
div[data-testid="stRadio"] > div > label:hover {
    border-color: #3b82f6 !important;
    background: rgba(59,130,246,0.12) !important;
}
div[data-testid="stRadio"] > div > label:has(input:checked) {
    border-color: #3b82f6 !important;
    background: rgba(59,130,246,0.18) !important;
}

/* ── Multiselect options ── */
div[data-testid="stMultiSelect"] span {
    font-size: 1.1rem !important;
}

/* ── Select slider ── */
div[data-testid="stSelectSlider"] label {
    font-size: 1rem !important;
    color: #f1f5f9 !important;
}

/* ── Slider: larger thumb ── */
div[data-testid="stSlider"] input[type=range] {
    height: 8px !important;
}

/* ── Headings: large and bold for mobile ── */
h1 { font-size: 2rem !important; }
h2 { font-size: 1.7rem !important; }
h3 { font-size: 1.4rem !important; }

/* ── Audio input: large record button ── */
div[data-testid="stAudioInput"] button {
    width: 100px !important;
    height: 100px !important;
    border-radius: 50% !important;
    font-size: 2.5rem !important;
}

/* ── Progress bar: thicker ── */
div[data-testid="stProgressBar"] > div {
    height: 10px !important;
    border-radius: 5px !important;
}

/* ── Caption / help text ── */
.stCaption, small { font-size: 1rem !important; }

/* ── Metric values ── */
div[data-testid="stMetric"] label { font-size: 1rem !important; }
div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
    font-size: 2.2rem !important;
    font-weight: 800 !important;
}

/* ── Text area + input: light text on dark bg ── */
textarea, input[type="text"], input[type="number"] {
    color: #f1f5f9 !important;
    background: #1e293b !important;
    border-color: #475569 !important;
}

/* ── Expander ── */
details summary p { font-size: 1.05rem !important; }
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
    demographics={},           # age_range + sex collected before AI questions
    demo_idx=0,                # index into DEMOGRAPHIC_QUESTIONS
    patient_photo=None,        # optional camera photo of wound/rash/swelling
    gps_fetched=False,         # GPS already fetched this session
    assessment=None,
    patient_record=None,
    eta_info=None,
    nearby_hospitals=[],
    selected_hospital=None,
    patient_lat=None,
    patient_lon=None,
    pre_arrival_advice=None,
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

    # Step 3: Collect demographics first, then generate AI questions
    # Demographics are reset here so each new complaint starts fresh
    st.session_state.demographics = {}
    st.session_state.demo_idx = 0
    st.session_state.q_idx = 0
    st.session_state.answers = []
    st.session_state.questions = []
    st.session_state.step = "demographics"
    st.rerun()


def try_transcribe(audio) -> str | None:
    """Attempt Azure Speech transcription of a Streamlit audio_input recording.

    ``st.audio_input`` returns raw browser audio bytes, typically in WebM/Opus
    format. Azure Speech SDK only accepts proper WAV (RIFF/PCM) files.
    This function detects the format, converts to WAV when needed, then
    calls recognition.

    Args:
        audio: Streamlit audio upload object with a ``.getvalue()`` method.

    Returns:
        Transcribed text string, or ``None`` if transcription failed.
    """
    if not speech_handler or not getattr(speech_handler, "_initialized", False):
        return None

    raw_bytes = audio.getvalue()
    if not raw_bytes:
        return None

    try:
        # Detect audio format by magic bytes
        # WebM starts with 0x1A 0x45 0xDF 0xA3 (EBML header)
        # WAV  starts with "RIFF"
        # OGG  starts with "OggS"
        is_wav = raw_bytes[:4] == b"RIFF"
        is_ogg = raw_bytes[:4] == b"OggS"
        is_webm = raw_bytes[:4] == b"\x1a\x45\xdf\xa3"

        if is_wav:
            # Already WAV — write directly and recognize
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp.write(raw_bytes)
                wav_path = tmp.name
            logger.info("Audio is already WAV format.")
        else:
            # Browser format (WebM/Opus, OGG, MP4…) — must convert to WAV
            src_suffix = ".ogg" if is_ogg else ".webm"
            logger.info(
                "Browser audio detected (is_webm=%s, is_ogg=%s). "
                "Converting to WAV via speech_handler...",
                is_webm, is_ogg,
            )
            wav_path = speech_handler.convert_browser_audio_to_wav(
                raw_bytes, source_suffix=src_suffix
            )
            if not wav_path:
                st.warning(
                    "⚠️ Could not convert audio to WAV format. "
                    "Please install **ffmpeg** on the server, or type your symptoms instead.\n\n"
                    "Install: `sudo apt-get install ffmpeg` (Linux) or "
                    "`brew install ffmpeg` (macOS)"
                )
                return None

        result = speech_handler.recognize_from_audio_file(wav_path)

        # Clean up temp WAV file
        try:
            os.unlink(wav_path)
        except OSError:
            pass

        if result and result.get("text"):
            detected_lang = result.get("language", "en-US")
            st.session_state.detected_language = detected_lang
            logger.info(
                "Transcribed: '%s' (language: %s)", result["text"][:60], detected_lang
            )
            return result["text"]

        # Recognition returned None — check logs for specific error code
        logger.warning("Azure Speech returned no text. Result: %s", result)
        st.warning(
            "⚠️ Azure Speech could not transcribe the audio.\n\n"
            "**Check the terminal for the exact error.** Common causes:\n"
            "- `SPEECH_KEY` is missing or wrong in `.env`\n"
            "- `SPEECH_REGION` does not match your Azure resource (e.g. `westeurope`)\n"
            "- Audio was too short or silent\n\n"
            "You can type your symptoms in the text box below."
        )

    except Exception as exc:
        logger.error("Transcription error: %s", exc)
        st.warning(f"⚠️ Transcription error: {exc}\n\nPlease type your symptoms below.")

    return None


# ---------------------------------------------------------------------------
# STEP 1: INPUT
# ---------------------------------------------------------------------------
def page_input() -> None:
    """Mobile-first voice input page.

    Designed for a patient holding a phone in distress.
    Primary action: speak into the microphone.
    Secondary action: type if voice unavailable.
    Demo shortcuts removed — real patients do not need them.
    """
    _inject_rtl_if_needed()

    # ── App header ────────────────────────────────────────────────────────
    st.markdown("""
<div style="text-align:center; padding: 1.5rem 0 0.5rem 0;">
  <div style="font-size:5rem; line-height:1;">🏥</div>
  <h1 style="font-size:2rem; font-weight:800; margin:0.3rem 0 0.2rem 0;">CodeZero</h1>
  <p style="font-size:1.1rem; color:#64748b; margin:0;">
    Tell us what's wrong — speak in any language
  </p>
</div>
""", unsafe_allow_html=True)

    # ── GPS: read coords written by JS into query params ─────────────────
    # Pure browser approach — no external package required.
    # On first page load the iframe script asks for location permission
    # and rewrites the URL with ?cz_lat=...&cz_lon=...
    # Streamlit picks up the new params on the next rerun.
    if not st.session_state.get("gps_fetched"):
        try:
            params = st.query_params
            if "cz_lat" in params and "cz_lon" in params:
                st.session_state.patient_lat = float(params["cz_lat"])
                st.session_state.patient_lon = float(params["cz_lon"])
                st.session_state.gps_fetched = True
        except Exception:
            pass

    if not st.session_state.get("gps_fetched"):
        st.components.v1.html("""
<script>
(function() {
  if (!navigator.geolocation) return;
  navigator.geolocation.getCurrentPosition(function(pos) {
    try {
      var url = new URL(window.parent.location.href);
      url.searchParams.set("cz_lat", pos.coords.latitude.toFixed(6));
      url.searchParams.set("cz_lon", pos.coords.longitude.toFixed(6));
      window.parent.location.replace(url.toString());
    } catch(e) {}
  }, function() {}, {timeout: 7000, enableHighAccuracy: false});
})();
</script>
""", height=0)

    # GPS status line
    if st.session_state.get("patient_lat"):
        st.markdown(
            '<p style="text-align:center;font-size:0.9rem;color:#16a34a;margin:0.1rem 0 0.5rem 0;">'
            '📍 Location detected</p>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<p style="text-align:center;font-size:0.9rem;color:#94a3b8;margin:0.1rem 0 0.5rem 0;">'
            '📍 Allow location when prompted</p>',
            unsafe_allow_html=True,
        )

    # ── Primary: voice input ──────────────────────────────────────────────
    if hasattr(st, "audio_input"):
        if "ffmpeg_available" not in st.session_state:
            import shutil
            st.session_state.ffmpeg_available = shutil.which("ffmpeg") is not None

        st.markdown("""
<div style="text-align:center; margin: 0.5rem 0 0.3rem 0;">
  <p style="font-size:1.2rem; font-weight:600; color:#1e293b; margin-bottom:0.2rem;">
    🎤 Tap the microphone and describe your symptoms
  </p>
  <p style="font-size:1rem; color:#64748b; margin:0;">
    Speak clearly — any language is understood
  </p>
</div>
""", unsafe_allow_html=True)

        audio = st.audio_input(" ", label_visibility="collapsed")

        if audio is not None:
            with st.spinner("🔄 Transcribing..."):
                transcribed = try_transcribe(audio)
            if transcribed:
                st.markdown(f"""
<div style="background:#f0fdf4; border:2px solid #22c55e; border-radius:14px;
     padding:1rem 1.2rem; margin:0.8rem 0; font-size:1.1rem;">
  ✅ <strong>Heard:</strong> {transcribed}
</div>
""", unsafe_allow_html=True)
                if st.button(
                    "▶  Start Assessment",
                    type="primary",
                    use_container_width=True,
                    key="btn_voice",
                ):
                    do_process(transcribed)
            else:
                st.warning("⚠️ Could not understand the audio. Please try again or type below.")
    else:
        st.info("Voice input requires Streamlit ≥ 1.41.0. Please type below.")

    # ── Optional: photo of wound / affected area ─────────────────────────
    # camera_input is guarded with try/except — some browsers block it
    # silently and cause a blank screen without the guard.
    try:
        if hasattr(st, "camera_input"):
            with st.expander("📷 Add a photo (optional)"):
                if not st.session_state.get("patient_photo"):
                    photo = st.camera_input(
                        "Take a photo of the affected area",
                        label_visibility="collapsed",
                    )
                    if photo is not None:
                        st.session_state.patient_photo = photo
                        st.success("✅ Photo saved.")
                else:
                    st.success("✅ Photo already captured.")
                    if st.button("Retake photo", key="retake_photo"):
                        st.session_state.patient_photo = None
                        st.rerun()
    except Exception:
        pass

    # ── Divider with "or" ─────────────────────────────────────────────────
    st.markdown("""
<div style="display:flex; align-items:center; gap:0.8rem; margin:1.2rem 0;">
  <hr style="flex:1; border:1px solid #e2e8f0; margin:0;">
  <span style="font-size:1rem; color:#94a3b8; white-space:nowrap;">or type</span>
  <hr style="flex:1; border:1px solid #e2e8f0; margin:0;">
</div>
""", unsafe_allow_html=True)

    # ── Secondary: text input ─────────────────────────────────────────────
    complaint = st.text_area(
        "Describe your symptoms",
        placeholder="e.g. I have severe chest pain and difficulty breathing",
        height=110,
        label_visibility="collapsed",
    )
    st.caption("🌍 Any language is auto-detected")

    if st.button("▶  Start Assessment", type="primary", use_container_width=True, key="btn_text"):
        if complaint and complaint.strip():
            do_process(complaint.strip())
        else:
            st.warning("Please describe your symptoms first.")


# ---------------------------------------------------------------------------
# STEP 1b: DEMOGRAPHICS
# ---------------------------------------------------------------------------
def page_demographics() -> None:
    """Collect age range and biological sex before generating AI questions.

    These two questions are asked once per triage session. The answers are
    stored in session_state.demographics and passed to generate_questions()
    so the AI can adapt clinical questions to the patient profile.
    """
    _inject_rtl_if_needed()

    st.title("🏥 Quick Patient Information")
    st.info(f"**Your concern:** {st.session_state.complaint_text}")
    st.caption("Two quick questions before we assess your symptoms.")

    demo_questions = DEMOGRAPHIC_QUESTIONS
    idx = st.session_state.demo_idx

    # All demographic questions answered — generate AI questions and proceed
    if idx >= len(demo_questions):
        with st.spinner("⚙️ Preparing your personalised assessment..."):
            if triage_engine:
                st.session_state.questions = triage_engine.generate_questions(
                    st.session_state.complaint_english,
                    demographics=st.session_state.demographics,
                )
            else:
                st.session_state.questions = []
        st.session_state.q_idx = 0
        st.session_state.step = "questions"
        st.rerun()
        return

    st.progress((idx) / len(demo_questions), text=f"Step {idx + 1} of {len(demo_questions)}")

    q = demo_questions[idx]
    q_text   = q.get("question", "")
    options  = q.get("options", [])

    st.markdown(f"### {t(q_text)}")

    answer = st.radio(
        "Select",
        [t(opt) for opt in options],
        key=f"demo_{idx}",
        horizontal=True,
    )

    if st.button("Next ➡", type="primary", use_container_width=True, key=f"demo_next_{idx}"):
        if answer:
            # Store demographic answer in english
            eng_answer = answer
            if translator:
                try:
                    eng_answer = translator.translate_to_english(answer, st.session_state.detected_language)
                except Exception:
                    pass

            # Map question to demographics dict key
            if idx == 0:
                st.session_state.demographics["age_range"] = eng_answer
            elif idx == 1:
                st.session_state.demographics["sex"] = eng_answer

            st.session_state.demo_idx += 1
            st.rerun()
        else:
            st.warning("Please select an answer.")


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
    options: list[str] = question.get("options", [])

    # Safety net: if AI returned free_text or empty options, convert to
    # sensible clickable defaults so the patient is never stuck.
    if q_type == "free_text" or not options:
        # Detect what kind of default options make sense from the question text
        q_lower = q_text.lower()
        if any(w in q_lower for w in ["when", "how long", "since", "start", "began", "zaman", "başla", "süre"]):
            q_type = "multiple_choice"
            options = ["Just now", "Less than 1 hour ago", "1–6 hours ago", "6–24 hours ago", "More than 1 day ago"]
        elif any(w in q_lower for w in ["how", "rate", "scale", "severity", "şiddet", "puan"]):
            q_type = "scale"
            options = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"]
        elif any(w in q_lower for w in ["where", "location", "nerede", "yer", "bölge"]):
            q_type = "multiple_choice"
            options = ["Head / neck", "Chest", "Abdomen", "Back", "Arms", "Legs", "All over"]
        elif any(w in q_lower for w in ["how did", "onset", "sudden", "gradual", "başlangıç", "ani"]):
            q_type = "multiple_choice"
            options = ["Suddenly", "Gradually over minutes", "Gradually over hours", "Gradually over days"]
        else:
            q_type = "yes_no"
            options = ["Yes", "No"]

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
        # yes_no and any unknown type — always render as radio with options
        if not options:
            options = ["Yes", "No"]
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

    # Patient-facing urgency message — no clinical jargon
    if level == TRIAGE_EMERGENCY:
        banner_bg    = "#7f1d1d"
        banner_border= "#dc2626"
        banner_icon  = "🚨"
        banner_title = "Please go to the emergency room immediately."
        banner_body  = "Your symptoms need urgent medical attention right now."
        time_hint    = "Every minute matters — please do not wait."
    elif level == TRIAGE_URGENT:
        banner_bg    = "#78350f"
        banner_border= "#d97706"
        banner_icon  = "⚠️"
        banner_title = "You need to go to hospital soon."
        banner_body  = "Your symptoms require medical evaluation within the next 30 minutes."
        time_hint    = "Please find the nearest hospital and go now."
    else:
        banner_bg    = "#14532d"
        banner_border= "#16a34a"
        banner_icon  = "ℹ️"
        banner_title = "You should see a doctor today."
        banner_body  = "Your symptoms are not immediately dangerous, but please get checked."
        time_hint    = "Visit a GP or urgent care clinic when convenient."

    st.markdown(f"""
<div style="background:{banner_bg}; border-left:5px solid {banner_border};
     border-radius:14px; padding:1.2rem 1.4rem; margin:0.5rem 0 1.2rem 0;">
  <p style="font-size:1.5rem; font-weight:800; margin:0 0 0.3rem 0; color:#f8fafc;">
    {banner_icon} {banner_title}
  </p>
  <p style="font-size:1.05rem; color:#e2e8f0; margin:0 0 0.3rem 0;">{banner_body}</p>
  <p style="font-size:0.95rem; color:#cbd5e1; margin:0;">{time_hint}</p>
</div>
""", unsafe_allow_html=True)

    st.subheader("📍 Find the nearest hospital")

    # Use GPS captured on the input page if available, else fall back to manual
    gps_lat = st.session_state.get("patient_lat")
    gps_lon = st.session_state.get("patient_lon")

    if gps_lat and gps_lon:
        st.success(f"📍 Location detected automatically ({gps_lat:.4f}, {gps_lon:.4f})")
        lat, lon = gps_lat, gps_lon
    else:
        st.caption("📍 GPS not available — enter your coordinates manually")
        loc_col1, loc_col2 = st.columns(2)
        with loc_col1:
            lat = st.number_input("Latitude", value=48.78, format="%.4f")
        with loc_col2:
            lon = st.number_input("Longitude", value=9.18, format="%.4f")

    # Auto-search if GPS already captured on input page and not yet searched
    if gps_lat and gps_lon and not st.session_state.nearby_hospitals:
        with st.spinner("📍 Finding nearest hospitals..."):
            if maps_handler:
                st.session_state.nearby_hospitals = maps_handler.find_nearest_hospitals(lat, lon, count=3)
                st.session_state.patient_lat = lat
                st.session_state.patient_lon = lon
            st.rerun()

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
            demographics=st.session_state.get("demographics"),
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

    # Attach photo flag (actual bytes not JSON-serializable but flag alerts staff)
    if st.session_state.get("patient_photo") is not None:
        record["has_photo"] = True
        record["photo_note"] = "Patient submitted a wound/symptom photo — review in app"

    if hospital_queue:
        hospital_queue.add_patient(record)

    st.session_state.patient_record = record

    # Generate pre-arrival DO / DON'T advice in the patient's language
    if triage_engine:
        try:
            advice = triage_engine.generate_pre_arrival_advice(
                chief_complaint=st.session_state.complaint_english,
                assessment=st.session_state.assessment,
                language=st.session_state.detected_language,
            )
            st.session_state.pre_arrival_advice = advice
        except Exception as exc:
            logger.error("Pre-arrival advice generation failed: %s", exc)
            st.session_state.pre_arrival_advice = None


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

    # ── Patient-friendly confirmation banner ──────────────────────────
    if level == TRIAGE_EMERGENCY:
        msg_title = "🚨 Hospital has been notified — go now!"
        msg_body  = "They are preparing for your arrival. Head to the emergency entrance immediately."
        banner_bg = "#7f1d1d"; banner_border = "#dc2626"
    elif level == TRIAGE_URGENT:
        msg_title = "✅ Hospital has been notified."
        msg_body  = "Please head there now and follow the instructions below before you leave."
        banner_bg = "#78350f"; banner_border = "#d97706"
    else:
        msg_title = "✅ Your details have been sent."
        msg_body  = "Please follow the instructions below and go to the hospital when ready."
        banner_bg = "#14532d"; banner_border = "#16a34a"

    st.markdown(f"""
<div style="background:{banner_bg}; border-left:5px solid {banner_border};
     border-radius:14px; padding:1.2rem 1.4rem; margin:0.5rem 0 1rem 0;">
  <p style="font-size:1.4rem; font-weight:800; margin:0 0 0.3rem 0; color:#f8fafc;">{msg_title}</p>
  <p style="font-size:1rem; color:#e2e8f0; margin:0;">{msg_body}</p>
</div>
""", unsafe_allow_html=True)

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
            '<div style="text-align:center; margin:1.5rem 0">'
            '<a href="tel:112" style="background:#dc2626; color:white; padding:18px 48px;'
            ' border-radius:12px; font-size:1.5rem; font-weight:700;'
            ' text-decoration:none; display:inline-block;">📞 CALL 112 NOW</a>'
            "</div>",
            unsafe_allow_html=True,
        )

    # ── Pre-arrival DO / DON'T advice card (patient-facing, in their language)
    advice = st.session_state.get("pre_arrival_advice")
    if advice:
        do_list   = advice.get("do_list", [])
        dont_list = advice.get("dont_list", [])

        if do_list or dont_list:
            border_color = {
                TRIAGE_EMERGENCY: "#dc2626",
                TRIAGE_URGENT:    "#d97706",
                TRIAGE_ROUTINE:   "#2563eb",
            }.get(level, "#d97706")

            st.markdown(f"""
<div style="border:2px solid {border_color}; border-radius:14px;
     padding:1.2rem 1.4rem; margin:1.2rem 0;">
""", unsafe_allow_html=True)
            st.markdown("### ⏱ Before You Arrive at Hospital")

            if do_list:
                st.markdown("**✅ DO:**")
                for item in do_list:
                    st.markdown(f"- {item}")

            if dont_list:
                st.markdown("**❌ DON'T:**")
                for item in dont_list:
                    st.markdown(f"- {item}")

            st.markdown("</div>", unsafe_allow_html=True)
    elif not advice:
        # Advice still generating or unavailable — show reassuring placeholder
        st.info("⏳ Personalised advice is being prepared...")

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
    if step == "demographics":
        page_demographics()
    elif step == "questions":
        page_questions()
    elif step == "location":
        page_location()
    elif step == "result":
        page_result()
    else:
        page_input()


if __name__ == "__main__":
    main()