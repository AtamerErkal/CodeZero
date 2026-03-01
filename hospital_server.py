"""
CodeZero — Hospital ER Command Center Server
============================================
FastAPI backend serving a real-time ER dashboard.

Run:
    pip install fastapi uvicorn
    python hospital_server.py

Then open: http://localhost:8001
"""
from __future__ import annotations

import base64
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ── path setup ────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

PATIENT_PHOTOS_DIR = ROOT / "patient_photos"
ILLNESS_PHOTOS_DIR = ROOT / "data" / "illness_photos"
ILLNESS_PHOTOS_DIR.mkdir(parents=True, exist_ok=True)

from src.hospital_queue import HospitalQueue
from src.health_db import (
    init_db, get_patient, get_age, get_full_record,
    list_demo_health_numbers,
)
from src.triage_engine import TRIAGE_EMERGENCY, TRIAGE_URGENT, TRIAGE_ROUTINE

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── init ──────────────────────────────────────────────────────────────────────
init_db()
hq = HospitalQueue()

# ── Migrate existing DB: add missing columns if not present ──────────────────
def _migrate_queue_db():
    """Add columns introduced after initial schema without breaking existing data."""
    import sqlite3 as _sq
    new_cols = [
        ("qa_transcript",  "TEXT DEFAULT '[]'"),
        ("complaint_text", "TEXT DEFAULT ''"),
        ("has_photo",      "INTEGER DEFAULT 0"),
        ("photo_count",    "INTEGER DEFAULT 0"),
        ("health_number",  "TEXT DEFAULT ''"),
    ]
    try:
        conn = _sq.connect(str(hq.db_path))
        existing = {row[1] for row in conn.execute("PRAGMA table_info(patient_queue)").fetchall()}
        for col, col_def in new_cols:
            if col not in existing:
                conn.execute(f"ALTER TABLE patient_queue ADD COLUMN {col} {col_def}")
                logger.info("DB migration: added column '%s'", col)
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning("DB migration warning: %s", e)

_migrate_queue_db()

app = FastAPI(title="CodeZero ER Dashboard", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

NAT_FLAG = {"DE": "🇩🇪", "TR": "🇹🇷", "UK": "🇬🇧", "GB": "🇬🇧"}


# ── schemas ───────────────────────────────────────────────────────────────────
from pydantic import BaseModel as _BM
from typing import Optional as _Opt, List as _List, Union as _Union

class QuestionsRequest(_BM):
    complaint:          str
    detected_language:  _Opt[str] = None
    demographics:       _Opt[dict] = None

class QuestionsResponse(_BM):
    questions:    list
    complaint_en: str

class AnswerItem(_BM):
    question:        str
    answer:          str
    original_answer: _Opt[str] = None

class AssessRequest(_BM):
    complaint:          str
    complaint_en:       _Opt[str] = None
    detected_language:  _Opt[str] = None
    questions:          _List[str] = []
    answers:            list = []
    demographics:       _Opt[dict] = None
    has_photo:          bool = False
    photo_count:        int = 0
    photo_base64:       _Opt[str] = None
    photo_mime:         _Opt[str] = None

class MediaItem(_BM):
    dataUrl: str
    mime:    _Opt[str] = None
    type:    _Opt[str] = None   # 'photo' | 'video'

class SubmitRequest(_BM):
    complaint:          str
    complaint_en:       _Opt[str] = None
    detected_language:  _Opt[str] = None
    assessment:         dict
    hospital:           _Opt[dict] = None
    lat:                _Opt[float] = None
    lon:                _Opt[float] = None
    answers:            list = []
    has_photo:          bool = False
    photo_count:        int = 0
    photo_base64:       _Opt[object] = None   # legacy: str | list[str]
    photo_mime:         _Opt[str] = None
    media:              _Opt[_List[MediaItem]] = None  # full media array with mime info
    reg_number:         _Opt[str] = None
    health_number:      _Opt[str] = None
    demographics:       _Opt[dict] = None
    data_consent:       _Opt[bool] = None

# ── helpers ───────────────────────────────────────────────────────────────────

def _enrich_patient(p: dict) -> dict:
    """Merge queue record with health-DB demographics and medical records."""
    hn = p.get("health_number") or p.get("hn", "")

    # Extra fields stored by patient_app but not in DB schema
    # (they travel as JSON in the record dict but aren't persisted)
    db = get_patient(hn) if hn else None
    if db:
        p["first_name"]  = db.get("first_name", "")
        p["last_name"]   = db.get("last_name", "")
        p["sex"]         = db.get("sex", p.get("sex", "—"))
        p["blood_type"]  = db.get("blood_type", "?")
        p["nationality"] = db.get("nationality", "")
        p["flag"]        = NAT_FLAG.get(db.get("nationality", ""), "🌍")
        p["age"]         = get_age(db.get("date_of_birth", ""))
        p["height_cm"]   = db.get("height_cm")
        p["weight_kg"]   = db.get("weight_kg")
        p["insurance_id"]= db.get("insurance_id", "")
        p["gp_name"]     = db.get("gp_name", "")
        p["phone"]       = db.get("phone", "")
        p["address"]     = db.get("address", "")
        p["notes"]       = db.get("notes", "")
        p["emergency_name"]  = db.get("emergency_name", "")
        p["emergency_phone"] = db.get("emergency_phone", "")
        p["full_name"]   = f"{db['first_name']} {db['last_name']}".strip()
        
        # PHASE 2: Add medical records from health_db
        try:
            full_record = get_full_record(hn)
            if full_record:
                # Diagnoses (medical history)
                p["diagnoses"] = full_record.get("diagnoses", [])
                
                # Active medications only
                all_meds = full_record.get("medications", [])
                p["medications"] = [m for m in all_meds if m.get("status") == "active"]
                
                # Latest vitals (most recent)
                vitals_list = full_record.get("vitals", [])
                if vitals_list:
                    latest = vitals_list[0]  # Already sorted by recorded_at DESC
                    p["vitals"] = {
                        "bp_systolic": latest.get("bp_systolic"),
                        "bp_diastolic": latest.get("bp_diastolic"),
                        "heart_rate": latest.get("heart_rate"),
                        "spo2": latest.get("spo2"),
                        "temperature": latest.get("temperature"),
                        "recorded_at": latest.get("recorded_at"),
                    }
                else:
                    p["vitals"] = {}
                
                # Allergies
                p["allergies"] = full_record.get("allergies", [])
                
                # Lab results (optional, for future use)
                p["lab_results"] = full_record.get("lab_results", [])[:5]  # Latest 5
                
                # Past visits (optional)
                p["visits"] = full_record.get("visits", [])[:3]  # Latest 3
        except Exception as e:
            logger.error("Health record enrich FAILED for %s: %s", hn, e, exc_info=True)
            p["diagnoses"] = []
            p["medications"] = []
            p["vitals"] = {}
            p["allergies"] = []
            p["lab_results"] = []
            p["visits"] = []
    else:
        # No health_number — use patient_id but keep visit-specific data from DB
        p["full_name"]   = p.get("patient_id", "Unknown Patient")
        p["flag"]        = "🌍"
        p["nationality"] = ""
        p["age"]         = p.get("age_range", "—")
        p["sex"]         = p.get("sex", "—")
        p["blood_type"]  = "?"
        p["diagnoses"]   = []
        p["medications"] = []
        p["vitals"]      = {}
        p["allergies"]   = []
        p["lab_results"] = []
        p["visits"]      = []

    # ETA
    eta = p.get("eta_minutes")
    if eta is not None:
        p["eta_display"] = f"{eta} min"
    elif p.get("arrival_time"):
        p["eta_display"] = "ARRIVED"
    else:
        p["eta_display"] = "—"

    # Location
    p["location"] = {
        "lat": p.pop("location_lat", None),
        "lon": p.pop("location_lon", None),
    }

    return p


# ── API endpoints ─────────────────────────────────────────────────────────────

@app.get("/api/stats")
def api_stats():
    """KPI bar data."""
    stats = hq.get_queue_stats()
    lvl   = stats.get("by_level", {})
    sts   = stats.get("by_status", {})

    en_route = sum(
        1 for p in hq.get_incoming_patients(limit=200)
        if p.get("eta_minutes") or p.get("arrival_time")
    )

    return {
        "total":      sum(sts.values()),
        "incoming":   sts.get("incoming", 0),
        "emergencies": lvl.get(TRIAGE_EMERGENCY, 0),
        "urgents":    lvl.get(TRIAGE_URGENT, 0),
        "routines":   lvl.get(TRIAGE_ROUTINE, 0),
        "en_route":   en_route,
        "treated":    sts.get("discharged", 0),
        "in_treatment": sts.get("in_treatment", 0),
    }


@app.get("/api/patients")
def api_patients(sort: str = "triage", limit: int = 50):
    """Incoming patient list, enriched with health DB data."""
    patients = hq.get_incoming_patients(limit=limit)
    enriched = [_enrich_patient(p) for p in patients]

    if sort == "eta":
        enriched.sort(key=lambda p: p.get("eta_minutes") or 9999)
    elif sort == "newest":
        enriched.sort(key=lambda p: p.get("timestamp", ""), reverse=True)
    elif sort == "oldest":
        enriched.sort(key=lambda p: p.get("timestamp", ""))
    # default: triage (already ordered by DB query)

    return enriched


@app.get("/api/patient/hospitals")
def patient_hospitals(lat: float, lon: float, country: str = "DE", n: int = 5):
    """Return nearest n hospitals with distance and ETA."""
    maps = _get_maps()
    try:
        hospitals = maps.find_nearest_hospitals(lat, lon, count=n, country=country)
        return hospitals
    except Exception as exc:
        logger.error("Hospital search error: %s", exc)
        # Fallback: compute straight-line distance from embedded list
        from src.maps_handler import GERMANY_HOSPITALS
        results = []
        for h in GERMANY_HOSPITALS:
            dist = _haversine(lat, lon, h["lat"], h["lon"])
            eta  = int(dist / 0.7)  # rough 42 km/h urban speed
            results.append({
                "name":        h["name"],
                "address":     h.get("address", ""),
                "lat":         h["lat"],
                "lon":         h["lon"],
                "distance_km": round(dist, 1),
                "eta_minutes": max(5, eta),
                "occupancy":   "",
            })
        results.sort(key=lambda x: x["distance_km"])
        return results[:n]


@app.post("/api/patient/submit")
def patient_submit(body: SubmitRequest):
    """Receive completed patient assessment and add to hospital queue.

    Mirrors Streamlit _do_notify():
      - Creates patient record via TriageEngine.create_patient_record()
      - Enriches with Q&A transcript, photo metadata, language, consent
      - Adds to HospitalQueue
    """
    triage, _ = _get_triage_engine()

    hospital  = body.hospital or {}
    eta       = hospital.get("eta_minutes")
    location  = {"lat": body.lat, "lon": body.lon} if body.lat else None

    record = triage.create_patient_record(
        chief_complaint=body.complaint_en or body.complaint,
        assessment=body.assessment,
        language=body.detected_language or "en-US",
        eta_minutes=eta,
        location=location,
        demographics=body.demographics,
    )

    # Override patient_id with registration number for dashboard display
    if body.reg_number:
        record["patient_id"] = body.reg_number

    # Enrich — mirrors Streamlit _do_notify() record enrichment
    # Normalize answers to list-of-dicts
    qa = []
    for a in (body.answers or []):
        if isinstance(a, dict):
            qa.append({"question": a.get("question",""), "answer": a.get("answer",""),
                       "original_answer": a.get("original_answer", a.get("originalAnswer",""))})
        elif hasattr(a, "question"):
            qa.append({"question": a.question, "answer": a.answer,
                       "original_answer": a.original_answer or a.answer})

    record["qa_transcript"]        = qa
    record["complaint_text"]       = body.complaint          # original-language text
    record["has_photo"]            = body.has_photo
    record["photo_count"]          = body.photo_count
    record["data_consent"]         = body.data_consent
    record["destination_hospital"] = hospital.get("name", "")   # FIXED: was target_hospital
    record["language"]             = body.detected_language or "en-US"  # FIXED: was detected_language
    record["location_lat"]         = body.lat
    record["location_lon"]         = body.lon
    record["status"]               = "incoming"

    # Flatten assessment dict from patient_app into top-level record fields
    # ALWAYS overwrite with patient_app AI assessment (more accurate than create_patient_record fallback)
    asmt_obj = body.assessment or {}
    if isinstance(asmt_obj, dict):
        # These fields come from /api/patient/assess (GPT-4) — always prefer them
        if asmt_obj.get("assessment"):
            record["assessment"] = asmt_obj["assessment"]
        if asmt_obj.get("suspected_conditions"):
            record["suspected_conditions"] = asmt_obj["suspected_conditions"]
        if asmt_obj.get("recommended_action"):
            record["recommended_action"] = asmt_obj["recommended_action"]
        if asmt_obj.get("time_sensitivity"):
            record["time_sensitivity"] = asmt_obj["time_sensitivity"]
        if asmt_obj.get("risk_score") is not None:
            record["risk_score"] = asmt_obj["risk_score"]
        if asmt_obj.get("red_flags"):
            record["red_flags"] = asmt_obj["red_flags"]
        if asmt_obj.get("triage_level"):
            record["triage_level"] = asmt_obj["triage_level"]
        # do_list / dont_list for pre-arrival advice
        if asmt_obj.get("do_list"):
            record["do_list"] = asmt_obj["do_list"]
        if asmt_obj.get("dont_list"):
            record["dont_list"] = asmt_obj["dont_list"]
        
        logger.info(
            "Assessment flattened: level=%s score=%s conds=%s",
            record.get("triage_level"),
            record.get("risk_score"),
            str(record.get("suspected_conditions", []))[:80],
        )

    # Link health DB record if health_number provided
    if body.health_number:
        record["health_number"] = body.health_number.strip().upper()

    # Save illness media (photos + videos) to disk
    pid = record["patient_id"]
    media_items = []

    # Prefer new 'media' array (has full mime info) over legacy photo_base64
    if body.media:
        media_items = [(m.dataUrl, m.mime or "image/jpeg", m.type or "photo")
                       for m in body.media]
    elif body.has_photo and body.photo_base64:
        photos_raw = body.photo_base64 if isinstance(body.photo_base64, list) else [body.photo_base64]
        for raw_url in photos_raw:
            mime = "image/jpeg"
            if raw_url.startswith("data:"):
                mime = raw_url.split(";")[0].replace("data:", "")
            kind = "video" if mime.startswith("video/") else "photo"
            media_items.append((raw_url, mime, kind))

    MIME_TO_EXT = {
        "image/jpeg": ".jpg", "image/jpg": ".jpg", "image/png": ".png",
        "image/webp": ".webp", "image/gif": ".gif",
        "video/mp4": ".mp4", "video/webm": ".webm", "video/quicktime": ".mov",
        "video/x-msvideo": ".avi",
    }
    import base64 as _b64
    for idx_m, (data_url, mime, kind) in enumerate(media_items):
        try:
            raw_b64 = data_url.split(",", 1)[-1] if "," in data_url else data_url
            ext = MIME_TO_EXT.get(mime, ".jpg" if kind == "photo" else ".webm")
            out_path = ILLNESS_PHOTOS_DIR / f"{pid}_{idx_m}{ext}"
            out_path.write_bytes(_b64.b64decode(raw_b64))
            logger.info("Saved media %d (%s) → %s", idx_m, kind, pid)
        except Exception as exc:
            logger.warning("Media %d save failed for %s: %s", idx_m, pid, exc)

    hq.add_patient(record)
    logger.info(
        "Patient submitted: %s → %s (lang=%s consent=%s)",
        record["patient_id"], hospital.get("name", ""),
        body.detected_language, body.data_consent,
    )

    return {"ok": True, "patient_id": record["patient_id"]}


@app.post("/api/patient/transcribe")
async def patient_transcribe(audio: UploadFile = File(...)):
    """Transcribe patient audio (WebM/Opus from browser) → text.

    Pipeline:
      1. Azure Speech SDK  (via src.speech_handler if available)
      2. OpenAI Whisper API (if OPENAI_API_KEY is set)
      3. Return empty → frontend falls back to Web Speech / manual typing
    """
    import os as _os, tempfile as _tmp

    raw = await audio.read()

    suffix = ".webm"
    if audio.filename:
        ext = _os.path.splitext(audio.filename)[1].lower()
        if ext in (".webm", ".ogg", ".mp4", ".wav", ".m4a"):
            suffix = ext

    # ── 1. Try Azure Speech SDK ───────────────────────────────────────────
    # Requires: SPEECH_KEY + SPEECH_REGION in .env, ffmpeg installed,
    #           azure-cognitiveservices-speech pip package
    speech_key = _os.getenv("SPEECH_KEY", "")
    if speech_key and speech_key != "your-key":
        try:
            # Ensure ffmpeg is on PATH for speech_handler (Windows venv PATH issue)
            import subprocess as _sp, shutil as _sh
            if not _sh.which("ffmpeg"):
                # Common Windows install locations
                _candidates = [
                    r"C:\ffmpeg\bin",
                    r"C:\Program Files\ffmpeg\bin",
                    r"C:\ProgramData\chocolatey\bin",
                    _os.path.expanduser(r"~\scoop\apps\ffmpeg\current\bin"),
                ]
                for _p in _candidates:
                    if _os.path.isfile(_os.path.join(_p, "ffmpeg.exe")):
                        _os.environ["PATH"] = _p + _os.pathsep + _os.environ.get("PATH","")
                        logger.info("Added ffmpeg to PATH: %s", _p)
                        break
                else:
                    # Last resort: ask Windows where ffmpeg is
                    try:
                        _r = _sp.run(["where", "ffmpeg"], capture_output=True, text=True, timeout=5)
                        if _r.returncode == 0:
                            _ffmpeg_path = _os.path.dirname(_r.stdout.strip().splitlines()[0])
                            _os.environ["PATH"] = _ffmpeg_path + _os.pathsep + _os.environ.get("PATH","")
                            logger.info("Found ffmpeg via 'where': %s", _ffmpeg_path)
                    except Exception:
                        pass

            from src.speech_handler import SpeechHandler as _SH
            speech = _SH()
            if speech._initialized:
                wav_path = speech.convert_browser_audio_to_wav(raw, source_suffix=suffix)
                if wav_path:
                    result = speech.recognize_from_audio_file(wav_path)
                    try:
                        _os.unlink(wav_path)
                    except Exception:
                        pass
                    if result and result.get("text", "").strip():
                        logger.info("Transcribed via Azure Speech: %s…", result["text"][:60])
                        return {"text": result["text"], "language": result.get("language", "en-US")}
                    else:
                        logger.warning("Azure Speech returned no text — falling back to Whisper")
                else:
                    logger.warning("Audio conversion failed (ffmpeg/pydub missing?) — falling back to Whisper")
            else:
                logger.warning("Azure Speech not initialized (check SPEECH_KEY/SPEECH_REGION) — falling back to Whisper")
        except ImportError:
            logger.warning("src.speech_handler not found — falling back to Whisper")
        except Exception as e:
            logger.warning("Azure Speech failed: %s — falling back to Whisper", e)
    else:
        logger.info("SPEECH_KEY not set — skipping Azure Speech, trying Whisper")

    # ── 2. OpenAI Whisper API ─────────────────────────────────────────────
    openai_key = _os.getenv("OPENAI_API_KEY", "")
    if openai_key:
        try:
            import openai as _oai

            with _tmp.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(raw)
                tmp_path = tmp.name

            client = _oai.OpenAI(api_key=openai_key)
            with open(tmp_path, "rb") as audio_file:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="verbose_json",
                )

            try:
                _os.unlink(tmp_path)
            except Exception:
                pass

            text = getattr(transcript, "text", "") or ""
            lang = getattr(transcript, "language", "en") or "en"

            LANG_MAP = {
                "tr": "tr-TR", "de": "de-DE", "en": "en-GB",
                "fr": "fr-FR", "es": "es-ES", "ar": "ar-SA",
                "it": "it-IT", "nl": "nl-NL", "ru": "ru-RU",
            }
            lang_bcp47 = LANG_MAP.get(lang, f"{lang}-{lang.upper()}")

            if text.strip():
                logger.info("Transcribed via Whisper: %s… (lang=%s)", text[:60], lang)
                return {"text": text.strip(), "language": lang_bcp47}
            else:
                logger.warning("Whisper returned empty text")
        except Exception as e:
            logger.warning("Whisper transcription failed: %s", e)
    else:
        logger.warning("OPENAI_API_KEY not set — Whisper unavailable")

    # ── 3. Nothing worked ─────────────────────────────────────────────────
    logger.info("All server transcription methods failed — frontend will use Web Speech")
    return {"text": "", "language": "en-US"}


@app.post("/api/patient/questions", response_model=QuestionsResponse)
def patient_questions(body: QuestionsRequest):
    """Translate complaint to English via Azure Translator, then generate
    GPT-4 clinical follow-up questions via TriageEngine.

    This mirrors the Streamlit flow:
      _do_process(): Azure Translator.translate_to_english()
      page_photos → _go_to_questions(): TriageEngine.generate_questions()
    """
    triage, translator = _get_triage_engine()

    # ── Step 1: Translate complaint to English (Azure Translator) ─────
    complaint_en = body.complaint
    if translator:
        try:
            # Pass detected language as source to improve translation accuracy
            result = translator.translate_to_english(
                body.complaint,
                source_language=body.detected_language,
            )
            if result:
                complaint_en = result
                logger.info(
                    "Complaint translated from %s to EN: '%s…'",
                    body.detected_language or "auto",
                    complaint_en[:60],
                )
        except Exception as exc:
            logger.warning("Translation failed (%s) — using original text.", exc)

    # ── Step 2: Generate GPT-4 clinical questions (TriageEngine) ──────
    # Determine target language name for GPT prompt injection
    lang_hint  = body.detected_language or "en-US"
    _lang_map  = {
        "tr": "Turkish", "de": "German",  "fr": "French",
        "es": "Spanish", "ar": "Arabic",  "nl": "Dutch",
        "it": "Italian", "pl": "Polish",  "pt": "Portuguese",
        "ru": "Russian", "zh": "Chinese",
    }
    lang_name = next((v for k, v in _lang_map.items() if lang_hint.lower().startswith(k)), None)

    # Inject language instruction into complaint so GPT generates questions in
    # the patient's language even when Azure Translator is not configured
    gpt_complaint = complaint_en
    if lang_name and not lang_hint.lower().startswith("en"):
        gpt_complaint = (
            f"[IMPORTANT: Generate ALL questions and ALL answer options ENTIRELY in {lang_name}. "
            f"Do not use English. Patient language: {lang_name}.] "
            f"{complaint_en}"
        )

    questions = triage.generate_questions(chief_complaint=gpt_complaint)
    logger.info("Generated %d questions (lang=%s): '%s…'", len(questions), lang_hint, complaint_en[:50])

    # ── Step 3: Azure Translator fallback (only if GPT language injection failed) ──
    if translator and lang_name and not lang_hint.lower().startswith("en"):
        for q in questions:
            # Only translate if question still appears to be in English
            q_text = q.get("question", "")
            looks_english = all(ord(c) < 128 for c in q_text.replace(" ", "")[:20])
            if not looks_english:
                continue   # Already in target language — skip translation
            try:
                translated_q = translator.translate_from_english(q_text, body.detected_language)
                if translated_q:
                    q["question"] = translated_q
            except Exception as exc:
                logger.warning("Question translation failed (%s)", exc)

            if "options" in q and q["options"]:
                translated_opts = []
                for opt in q["options"]:
                    try:
                        opt_looks_en = all(ord(c) < 128 for c in opt.replace(" ", "")[:10])
                        if opt_looks_en:
                            translated_opt = translator.translate_from_english(opt, body.detected_language)
                            translated_opts.append(translated_opt if translated_opt else opt)
                        else:
                            translated_opts.append(opt)
                    except Exception:
                        translated_opts.append(opt)
                q["options"] = translated_opts

    return QuestionsResponse(questions=questions, complaint_en=complaint_en)


@app.post("/api/patient/assess")
def patient_assess(body: AssessRequest):
    """Translate patient answers to English, run GPT-4 triage assessment,
    and generate pre-arrival DO/DON'T advice.

    Mirrors Streamlit flow:
      page_questions: translator.translate_to_english(answer)
      _page_consent: triage_engine.assess_triage()
      _do_notify:    triage_engine.generate_pre_arrival_advice()
    """
    triage, translator = _get_triage_engine()

    complaint_en = body.complaint_en or body.complaint

    # ── Step 1: Translate answers to English (Azure Translator) ───────
    # Mirrors Streamlit: eng = translator.translate_to_english(str(answer), lang)
    qa_pairs = []
    for item in body.answers:
        if isinstance(item, dict):
            q   = item.get("question", "")
            ans = item.get("answer", item.get("original_answer", ""))
        else:
            continue

        if not ans:
            continue

        # Translate answer to English for accurate GPT-4 assessment
        ans_en = str(ans)
        if translator and body.detected_language and not body.detected_language.startswith("en"):
            try:
                translated = translator.translate_to_english(
                    str(ans),
                    source_language=body.detected_language,
                )
                if translated:
                    ans_en = translated
            except Exception as exc:
                logger.warning("Answer translation failed (%s) — using original.", exc)

        qa_pairs.append({"question": q, "answer": ans_en})

    logger.info(
        "Assessing triage: complaint='%s…', %d Q&A pairs, lang=%s",
        complaint_en[:50], len(qa_pairs), body.detected_language or "en",
    )

    # ── Step 2: GPT-4 triage assessment (TriageEngine) ─────────────────
    assessment = triage.assess_triage(
        chief_complaint=complaint_en,
        answers=qa_pairs,
    )

    # ── Step 3: Generate pre-arrival DO/DON'T advice (GPT-4 + RAG) ────
    # Mirrors Streamlit _do_notify() → generate_pre_arrival_advice()
    advice = triage.generate_pre_arrival_advice(
        chief_complaint=complaint_en,
        assessment=assessment,
        language=body.detected_language or "en-US",
    )
    assessment["do_list"]   = advice.get("do_list",   [])
    assessment["dont_list"] = advice.get("dont_list", [])

    logger.info(
        "Assessment done: level=%s score=%s do=%d dont=%d",
        assessment.get("triage_level"),
        assessment.get("risk_score"),
        len(assessment["do_list"]),
        len(assessment["dont_list"]),
    )

    return assessment


@app.get("/api/patient/{patient_id}")
def api_patient_detail(patient_id: str):
    """Single patient full detail."""
    all_p = hq.get_all_patients(limit=200)
    match = next((p for p in all_p if p["patient_id"] == patient_id), None)
    if not match:
        raise HTTPException(404, "Patient not found")
    return _enrich_patient(match)


@app.get("/api/health_record/{health_number}")
def api_health_record(health_number: str):
    """Full health record from health DB."""
    rec = get_full_record(health_number)
    if not rec or not rec.get("patient"):
        raise HTTPException(404, "Health record not found")
    return rec


@app.patch("/api/patient/{patient_id}/status")
def api_update_status(patient_id: str, body: dict):
    """Update patient status (incoming → arrived → in_treatment → discharged)."""
    status = body.get("status")
    valid  = {"incoming", "arrived", "in_treatment", "discharged"}
    if status not in valid:
        raise HTTPException(400, f"Invalid status. Must be one of: {valid}")
    ok = hq.update_status(patient_id, status)
    if not ok:
        raise HTTPException(500, "Failed to update status")
    return {"ok": True, "patient_id": patient_id, "status": status}



@app.get("/api/patient_photo/{health_number}")
def serve_patient_photo(health_number: str):
    for ext in (".png", ".jpg", ".jpeg", ".webp"):
        p = PATIENT_PHOTOS_DIR / f"{health_number}{ext}"
        if p.exists():
            mime = "image/jpeg" if ext in (".jpg",".jpeg") else f"image/{ext.lstrip('.')}"
            return Response(p.read_bytes(), media_type=mime, headers={"Cache-Control":"max-age=86400"})
    raise HTTPException(404, "Profile photo not found")


@app.get("/api/illness_photo/{patient_id}/{index}")
def serve_illness_photo(patient_id: str, index: int = 0):
    """Serve illness media — images and videos."""
    MEDIA_EXTS = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png",  ".webp": "image/webp",
        ".gif": "image/gif",
        ".mp4": "video/mp4",  ".webm": "video/webm",
        ".mov": "video/quicktime", ".avi": "video/x-msvideo",
    }
    for ext, mime in MEDIA_EXTS.items():
        p = ILLNESS_PHOTOS_DIR / f"{patient_id}_{index}{ext}"
        if p.exists():
            return Response(p.read_bytes(), media_type=mime,
                            headers={"Cache-Control": "max-age=300"})
    raise HTTPException(404, "Illness media not found")


@app.get("/api/illness_photo/{patient_id}/{index}/type")
def get_illness_media_type(patient_id: str, index: int = 0):
    """Return the mime type of a media file without streaming the whole file."""
    VIDEO_EXTS = {".mp4", ".webm", ".mov", ".avi"}
    IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
    for ext in list(VIDEO_EXTS) + list(IMAGE_EXTS):
        p = ILLNESS_PHOTOS_DIR / f"{patient_id}_{index}{ext}"
        if p.exists():
            kind = "video" if ext in VIDEO_EXTS else "image"
            return {"kind": kind, "ext": ext}
    raise HTTPException(404, "Not found")

@app.get("/api/tracking")
def api_tracking():
    """All patients with GPS for live map."""
    patients = hq.get_incoming_patients(limit=200)
    enriched = [_enrich_patient(p) for p in patients]
    return [p for p in enriched if p["location"].get("lat")]


@app.post("/api/admin/clear")
def api_clear():
    """Clear all patients (testing only)."""
    hq.clear_queue()
    return {"ok": True}


@app.post("/api/admin/seed")
def api_seed():
    """Seed realistic test patients."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    test_patients = [
        {"patient_id": "ER-2026-AA01", "triage_level": "EMERGENCY",
         "chief_complaint": "Crushing chest pain radiating to left arm",
         "assessment": "Suspected STEMI. Immediate cath lab activation required. Patient diaphoretic, BP 85/50.",
         "red_flags": ["chest_pain_radiation", "diaphoresis", "hypotension"],
         "risk_score": 10, "suspected_conditions": ["STEMI", "ACS"],
         "recommended_action": "Activate cath lab. 12-lead ECG. Aspirin 300mg. IV access x2.",
         "time_sensitivity": "Within 5 minutes", "eta_minutes": 4,
         "health_number": "DEMO-DE-001", "location": {"lat": 48.77, "lon": 9.18},
         "destination_hospital": "Klinikum Stuttgart", "language": "de-DE",
         "data_consent": True, "has_photo": False, "photo_count": 0,
         "complaint_text": "Starke Brustschmerzen die in den linken Arm ausstrahlen",
         "qa_transcript": [
             {"question": "When did it start?", "answer": "15 minutes ago", "original_answer": "Vor 15 Minuten"},
             {"question": "Rate pain 1-10?", "answer": "9", "original_answer": "9"},
             {"question": "Any shortness of breath?", "answer": "Yes", "original_answer": "Ja, sehr"},
         ], "timestamp": now},

        {"patient_id": "ER-2026-BB02", "triage_level": "EMERGENCY",
         "chief_complaint": "Thunderclap headache, worst of life, sudden onset",
         "assessment": "Possible subarachnoid hemorrhage. Immediate CT head required. GCS 14.",
         "red_flags": ["sudden_severe_headache", "vomiting", "photophobia", "neck_stiffness"],
         "risk_score": 9, "suspected_conditions": ["Subarachnoid Hemorrhage", "Meningitis"],
         "recommended_action": "Immediate CT head non-contrast. Lumbar puncture if CT negative.",
         "time_sensitivity": "Within 10 minutes", "eta_minutes": 7,
         "health_number": "DEMO-TR-001", "location": {"lat": 48.79, "lon": 9.20},
         "destination_hospital": "Klinikum Stuttgart", "language": "tr-TR",
         "data_consent": True, "has_photo": True, "photo_count": 1,
         "complaint_text": "Hayatımda yaşadığım en kötü baş ağrısı, aniden geldi",
         "qa_transcript": [
             {"question": "When did it start?", "answer": "Suddenly 20 min ago", "original_answer": "Aniden, 20 dakika önce"},
             {"question": "Any visual changes?", "answer": "Yes, blurry", "original_answer": "Evet, bulanık görüyorum"},
             {"question": "Any vomiting?", "answer": "Yes, twice", "original_answer": "Evet, iki kez"},
         ], "timestamp": now},

        {"patient_id": "ER-2026-CC03", "triage_level": "URGENT",
         "chief_complaint": "Severe abdominal pain after blunt trauma",
         "assessment": "Blunt abdominal trauma. Possible splenic laceration. Rigid board-like abdomen.",
         "red_flags": ["rigid_abdomen", "post_trauma", "tachycardia"],
         "risk_score": 8, "suspected_conditions": ["Splenic Laceration", "Internal Bleeding"],
         "recommended_action": "FAST ultrasound. Trauma surgery consult. 2x large bore IV. Cross-match.",
         "time_sensitivity": "Within 30 minutes", "eta_minutes": 12,
         "health_number": "DEMO-UK-001", "location": {"lat": 48.81, "lon": 9.15},
         "destination_hospital": "Klinikum Stuttgart", "language": "en-GB",
         "data_consent": True, "has_photo": True, "photo_count": 2,
         "complaint_text": "Really bad stomach pain after being hit by a car door at the car park",
         "qa_transcript": [
             {"question": "Where is the pain?", "answer": "Left abdomen", "original_answer": "Left abdomen"},
             {"question": "Rate pain 1-10?", "answer": "8", "original_answer": "8"},
         ], "timestamp": now},

        {"patient_id": "ER-2026-DD04", "triage_level": "URGENT",
         "chief_complaint": "Acute asthma exacerbation, difficulty breathing",
         "assessment": "Moderate asthma exacerbation. SpO2 91% on air. Audible wheeze bilateral.",
         "red_flags": ["low_spo2", "respiratory_distress"],
         "risk_score": 7, "suspected_conditions": ["Asthma Exacerbation", "COPD"],
         "recommended_action": "Nebulised salbutamol 5mg. Oral prednisolone 40mg. O2 titrate to 94-98%.",
         "time_sensitivity": "Within 20 minutes", "eta_minutes": 15,
         "health_number": "DEMO-TR-002", "location": {"lat": 48.76, "lon": 9.22},
         "destination_hospital": "Klinikum Stuttgart", "language": "tr-TR",
         "data_consent": True, "has_photo": False, "photo_count": 0,
         "complaint_text": "Nefes almakta çok zorlanıyorum, ciğerlerim sıkışmış gibi",
         "qa_transcript": [
             {"question": "Do you have an inhaler?", "answer": "Yes but not helping", "original_answer": "Var ama işe yaramıyor"},
             {"question": "How long?", "answer": "1 hour", "original_answer": "1 saattir"},
         ], "timestamp": now},

        {"patient_id": "ER-2026-EE05", "triage_level": "ROUTINE",
         "chief_complaint": "Mild headache and dizziness since this morning",
         "assessment": "Likely tension headache with mild dehydration. No neurological signs. BP normal.",
         "red_flags": [], "risk_score": 2,
         "suspected_conditions": ["Tension Headache", "Dehydration"],
         "recommended_action": "Oral hydration. Paracetamol 1g. Reassess in 1 hour.",
         "time_sensitivity": "Within 2 hours", "eta_minutes": 28,
         "health_number": "DEMO-DE-003", "location": {"lat": 48.74, "lon": 9.16},
         "destination_hospital": "Klinikum Stuttgart", "language": "de-DE",
         "data_consent": True, "has_photo": False, "photo_count": 0,
         "complaint_text": "Leichte Kopfschmerzen und Schwindel seit dem Morgen",
         "qa_transcript": [
             {"question": "How long?", "answer": "Since morning", "original_answer": "Seit dem Morgen"},
             {"question": "Any fever?", "answer": "No", "original_answer": "Nein"},
         ], "timestamp": now},
    ]
    for tp in test_patients:
        hq.add_patient(tp)
    return {"ok": True, "seeded": len(test_patients)}




@app.get("/api/debug/health")
def debug_health_db():
    """Debug: show health_records.db status. Visit /api/debug/health in browser."""
    try:
        from src.health_db import _conn as hdb_conn, DB_PATH as HDB_PATH
        with hdb_conn() as con:
            patients = con.execute("SELECT COUNT(*) FROM patients").fetchone()[0]
            vitals   = con.execute("SELECT COUNT(*) FROM vitals").fetchone()[0]
            diags    = con.execute("SELECT COUNT(*) FROM diagnoses").fetchone()[0]
            meds     = con.execute("SELECT COUNT(*) FROM medications").fetchone()[0]
        return {
            "db_path": str(HDB_PATH),
            "db_exists": Path(str(HDB_PATH)).exists(),
            "patients": patients, "vitals": vitals,
            "diagnoses": diags, "medications": meds,
            "status": "OK" if vitals > 0 and diags > 0 else "NEEDS_RESEED — call POST /api/admin/reseed_health",
        }
    except Exception as e:
        return {"error": str(e), "status": "ERROR"}

@app.post("/api/admin/reseed_health")
def api_reseed_health():
    """Force re-seed vitals/diagnoses/medications if they were empty."""
    try:
        from src.health_db import _conn as hdb_conn, _seed as hdb_seed
        with hdb_conn() as con:
            for tbl in ("vitals","diagnoses","medications","lab_results","allergies","visits"):
                con.execute(f"DELETE FROM {tbl}")
            hdb_seed(con)
        return {"ok": True, "message": "Health records re-seeded"}
    except Exception as e:
        raise HTTPException(500, f"Re-seed failed: {e}")

# ── Serve the dashboard HTML ──────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def serve_dashboard():
    # Support both legacy and modern dashboard names, in multiple locations
    for candidate in [
        ROOT / "ui" / "hospital_dashboard_v1.html",
        ROOT / "ui" / "hospital_dashboard.html",
    ]:
        if candidate.exists():
            return HTMLResponse(candidate.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Dashboard HTML not found</h1><p>Run the build step first.</p>", status_code=404)


@app.get("/patient", response_class=HTMLResponse)
def serve_patient_app():
    # Try versioned and unversioned filenames in ui/ and root
    candidates = [
        ROOT / "ui" / "patient_app_v1.html",
        ROOT / "patient_app_v1.html",
        ROOT / "ui" / "patient_app.html",
        ROOT / "patient_app.html",
    ]
    for path in candidates:
        if path.exists():
            return HTMLResponse(path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Patient app HTML not found</h1>", status_code=404)


@app.get("/patient_app_v1.html", response_class=HTMLResponse)
def serve_patient_app_v1():
    """Direct filename access — ngrok/browser convenience."""
    return serve_patient_app()


@app.get("/patient_app.html", response_class=HTMLResponse)
def serve_patient_app_plain():
    """Direct filename access — ngrok/browser convenience."""
    return serve_patient_app()


# ══════════════════════════════════════════════════════════════════════════════
# PATIENT APP APIs
# ══════════════════════════════════════════════════════════════════════════════

# Lazy-init services (only when first patient API call arrives)
_patient_services: dict = {}


def _get_triage_engine():
    if "triage" not in _patient_services:
        from src.triage_engine import TriageEngine
        from src.translator import Translator
        from src.knowledge_indexer import KnowledgeIndexer
        try:
            ki = KnowledgeIndexer()
        except Exception:
            ki = None
        try:
            tr = Translator()
        except Exception:
            tr = None
        _patient_services["triage"]     = TriageEngine(knowledge_indexer=ki, translator=tr)
        _patient_services["translator"] = tr
    return _patient_services["triage"], _patient_services.get("translator")


def _get_speech():
    if "speech" not in _patient_services:
        from src.speech_handler import SpeechHandler
        _patient_services["speech"] = SpeechHandler()
    return _patient_services["speech"]


def _get_maps():
    if "maps" not in _patient_services:
        from src.maps_handler import MapsHandler
        _patient_services["maps"] = MapsHandler()
    return _patient_services["maps"]


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import os as _os_check, shutil

    speech_key  = _os_check.getenv("SPEECH_KEY", "")
    openai_key  = _os_check.getenv("OPENAI_API_KEY", "")
    # shutil.which can miss ffmpeg on Windows venvs — verify with subprocess
    try:
        import subprocess as _sp
        _sp.run(["ffmpeg", "-version"], capture_output=True, timeout=5, check=True)
        ffmpeg_ok = True
    except Exception:
        ffmpeg_ok = False

    def _status(ok): return "✅" if ok else "❌"

    print("\n" + "═" * 58)
    print("  🏥  CodeZero — ER Command Center")
    print("═" * 58)
    print(f"  ➜  Dashboard :  http://localhost:8001")
    print(f"  ➜  Patient   :  http://localhost:8001/patient")
    print(f"  ➜  API docs  :  http://localhost:8001/docs")
    print(f"  ➜  DB path   :  {hq.db_path}")
    print("─" * 58)
    print("  🎙️  Transcription pipeline:")
    print(f"    {_status(bool(speech_key))} Azure Speech  (SPEECH_KEY {'set' if speech_key else 'NOT SET'})")
    print(f"    {_status(ffmpeg_ok)} ffmpeg       ({'found' if ffmpeg_ok else 'NOT FOUND — audio conversion will fail'})")
    print(f"    {_status(bool(openai_key))} Whisper      (OPENAI_API_KEY {'set' if openai_key else 'NOT SET'})")
    if not speech_key and not openai_key:
        print("    ⚠️  No transcription backend configured!")
        print("    ⚠️  Set SPEECH_KEY or OPENAI_API_KEY in .env")
    print("═" * 58 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=8001, reload=False, log_level="info")