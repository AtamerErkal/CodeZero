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

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# ── path setup ────────────────────────────────────────────────────────────────
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

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
from typing import Optional as _Opt, List as _List

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
    reg_number:         _Opt[str] = None
    demographics:       _Opt[dict] = None
    data_consent:       _Opt[bool] = None

# ── helpers ───────────────────────────────────────────────────────────────────

def _enrich_patient(p: dict) -> dict:
    """Merge queue record with health-DB demographics."""
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
    else:
        p["full_name"]   = p.get("patient_id", "Unknown")
        p["flag"]        = "🌍"
        p["nationality"] = ""
        p["age"]         = p.get("age_range", "—")

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
    record["qa_transcript"]       = body.answers
    record["complaint_text"]      = body.complaint        # original language
    record["has_photo"]           = body.has_photo
    record["photo_count"]         = body.photo_count
    record["data_consent"]        = body.data_consent
    record["target_hospital"]     = hospital.get("name", "")
    record["location_lat"]        = body.lat
    record["location_lon"]        = body.lon
    record["status"]              = "incoming"
    record["detected_language"]   = body.detected_language or "en-US"

    hq.add_patient(record)
    logger.info(
        "Patient submitted: %s → %s (lang=%s consent=%s)",
        record["patient_id"], hospital.get("name", ""),
        body.detected_language, body.data_consent,
    )

    return {"ok": True, "patient_id": record["patient_id"]}


@app.post("/api/patient/transcribe")
async def patient_transcribe(audio: UploadFile = File(...)):
    """Transcribe patient audio (WebM/Opus from browser) → text."""
    raw = await audio.read()
    speech = _get_speech()

    suffix = ".webm"
    if audio.filename:
        ext = os.path.splitext(audio.filename)[1].lower()
        if ext in (".webm", ".ogg", ".mp4", ".wav", ".m4a"):
            suffix = ext

    wav_path = speech.convert_browser_audio_to_wav(raw, source_suffix=suffix)

    if wav_path:
        result = speech.recognize_from_audio_file(wav_path)
        try:
            os.unlink(wav_path)
        except Exception:
            pass
        if result:
            return {"text": result.get("text", ""), "language": result.get("language", "en-US")}

    # Fallback: return empty so frontend falls back to manual typing
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
    questions = triage.generate_questions(chief_complaint=complaint_en)
    logger.info("Generated %d questions for complaint: '%s…'", len(questions), complaint_en[:50])

    # ── Step 3: Translate questions back to detected language (if not English) ──
    if translator and body.detected_language and not body.detected_language.startswith("en"):
        for q in questions:
            try:
                translated_q = translator.translate_from_english(q["question"], body.detected_language)
                if translated_q:
                    q["question"] = translated_q
            except Exception as exc:
                logger.warning("Question translation failed (%s)", exc)
            
            if "options" in q and q["options"]:
                translated_opts = []
                for opt in q["options"]:
                    try:
                        translated_opt = translator.translate_from_english(opt, body.detected_language)
                        translated_opts.append(translated_opt if translated_opt else opt)
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


# ── Serve the dashboard HTML ──────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def serve_dashboard():
    html_path = ROOT / "ui" / "hospital_dashboard.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Dashboard HTML not found</h1><p>Run the build step first.</p>", status_code=404)


@app.get("/patient", response_class=HTMLResponse)
def serve_patient_app():
    html_path = ROOT / "ui" / "patient_app.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Patient app HTML not found</h1>", status_code=404)


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


# ── POST /api/patient/transcribe ──────────────────────────────────────────────
from fastapi import UploadFile, File
import tempfile, os


@app.post("/api/patient/transcribe")
async def patient_transcribe(audio: UploadFile = File(...)):
    """Transcribe patient audio (WebM/Opus from browser) → text."""
    raw = await audio.read()
    speech = _get_speech()

    suffix = ".webm"
    if audio.filename:
        ext = os.path.splitext(audio.filename)[1].lower()
        if ext in (".webm", ".ogg", ".mp4", ".wav", ".m4a"):
            suffix = ext

    wav_path = speech.convert_browser_audio_to_wav(raw, source_suffix=suffix)

    if wav_path:
        result = speech.recognize_from_audio_file(wav_path)
        try:
            os.unlink(wav_path)
        except Exception:
            pass
        if result:
            return {"text": result.get("text", ""), "language": result.get("language", "en-US")}

    # Fallback: return empty so frontend falls back to manual typing
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
    questions = triage.generate_questions(chief_complaint=complaint_en)
    logger.info("Generated %d questions for complaint: '%s…'", len(questions), complaint_en[:50])

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


# ── GET /api/patient/hospitals ────────────────────────────────────────────────
import math as _math


def _haversine(lat1, lon1, lat2, lon2) -> float:
    R = 6371.0
    dlat = _math.radians(lat2 - lat1)
    dlon = _math.radians(lon2 - lon1)
    a = (_math.sin(dlat / 2) ** 2
         + _math.cos(_math.radians(lat1)) * _math.cos(_math.radians(lat2))
         * _math.sin(dlon / 2) ** 2)
    return R * 2 * _math.atan2(_math.sqrt(a), _math.sqrt(1 - a))


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
    record["qa_transcript"]       = body.answers
    record["complaint_text"]      = body.complaint        # original language
    record["has_photo"]           = body.has_photo
    record["photo_count"]         = body.photo_count
    record["data_consent"]        = body.data_consent
    record["target_hospital"]     = hospital.get("name", "")
    record["location_lat"]        = body.lat
    record["location_lon"]        = body.lon
    record["status"]              = "incoming"
    record["detected_language"]   = body.detected_language or "en-US"

    hq.add_patient(record)
    logger.info(
        "Patient submitted: %s → %s (lang=%s consent=%s)",
        record["patient_id"], hospital.get("name", ""),
        body.detected_language, body.data_consent,
    )

    return {"ok": True, "patient_id": record["patient_id"]}


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "═" * 58)
    print("  🏥  CodeZero — ER Command Center")
    print("═" * 58)
    print(f"  ➜  Dashboard:  http://localhost:8001")
    print(f"  ➜  API docs:   http://localhost:8001/docs")
    print(f"  ➜  DB path:    {hq.db_path}")
    print("═" * 58 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=8001, reload=False, log_level="warning")