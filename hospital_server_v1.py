"""
VitalNavAI â€” Hospital ER Command Center Server
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
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# â”€â”€ path setup â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

PATIENT_PHOTOS_DIR = ROOT / "patient_photos"
ILLNESS_PHOTOS_DIR = ROOT / "data" / "illness_photos"
ILLNESS_PHOTOS_DIR.mkdir(parents=True, exist_ok=True)

from src.hospital_queue import HospitalQueue
from src.health_db_v1 import (
    get_patient, get_full_record, get_age, list_demo_health_numbers
)
from src.triage_engine import TRIAGE_EMERGENCY, TRIAGE_URGENT, TRIAGE_ROUTINE

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# â”€â”€ init â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# init_db() # Removed as per new health_db_v1 import
hq = HospitalQueue()

# â”€â”€ Migrate existing DB: add missing columns if not present â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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


app = FastAPI(title="VitalNavAI ER Dashboard", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi.staticfiles import StaticFiles
docs_dir = ROOT / "docs"
if docs_dir.exists():
    app.mount("/docs", StaticFiles(directory=str(docs_dir)), name="docs")

NAT_FLAG = {"DE": "🇩🇪", "TR": "🇹🇷", "UK": "🇬🇧", "GB": "🇬🇧"}

# ── Hospital location (Ulm Uni Klinik) ──────────────────────────────────────
HOSPITAL_LAT = 48.4215
HOSPITAL_LON = 9.9593

# ── Background thread: move patients toward hospital every 5 seconds ─────────
import threading as _threading
import math as _math
import sqlite3 as _sqlite3

def _move_patients_loop():
    """Background daemon: moves all incoming patients toward the hospital."""
    TICK = 5          # seconds between ticks
    LAT_KM = 111.0    # km per degree latitude
    LON_KM = 72.0     # km per degree longitude at 48°N
    SPEED_KM_MIN = 60.0 / 60.0  # 60 km/h = 1 km/min
    ARRIVE_DIST_KM = 0.05  # 50 m threshold → arrived

    import datetime as _dt

    while True:
        _threading.Event().wait(TICK)
        try:
            conn = _sqlite3.connect(str(hq.db_path))
            conn.row_factory = _sqlite3.Row
            rows = conn.execute(
                "SELECT patient_id, location_lat, location_lon, eta_minutes "
                "FROM patient_queue WHERE status = 'incoming' AND location_lat IS NOT NULL"
            ).fetchall()

            now_iso = _dt.datetime.now(_dt.timezone.utc).isoformat()

            for row in rows:
                pid = row["patient_id"]
                lat = row["location_lat"]
                lon = row["location_lon"]

                # Actual remaining distance (in km)
                dlat = HOSPITAL_LAT - lat
                dlon = HOSPITAL_LON - lon
                dist_km = _math.sqrt((dlat * LAT_KM) ** 2 + (dlon * LON_KM) ** 2)

                if dist_km <= ARRIVE_DIST_KM:
                    conn.execute(
                        "UPDATE patient_queue SET status='in_treatment', eta_minutes=NULL, "
                        "arrival_time=?, treatment_started_at=?, updated_at=? WHERE patient_id=?",
                        (now_iso, now_iso, now_iso, pid)
                    )
                    logger.info("Patient %s → in_treatment (auto-arrived).", pid)
                    continue

                # Move: distance covered this tick at constant 60 km/h
                step_km = SPEED_KM_MIN * (TICK / 60.0)
                frac = min(1.0, step_km / dist_km)
                new_lat = lat + dlat * frac
                new_lon = lon + dlon * frac

                # Re-derive ETA from new remaining distance (always a clean integer)
                new_dist_km = dist_km * (1.0 - frac)
                new_eta = max(1, round(new_dist_km / SPEED_KM_MIN))  # integer minutes

                conn.execute(
                    "UPDATE patient_queue SET location_lat=?, location_lon=?, eta_minutes=?, "
                    "updated_at=? WHERE patient_id=?",
                    (new_lat, new_lon, new_eta, now_iso, pid)
                )

            conn.commit()
            conn.close()
        except Exception as _e:
            logger.warning("Patient movement tick error: %s", _e)

logger.info("Patient movement background thread started.")


# â”€â”€ schemas â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
from pydantic import BaseModel as _BM
from typing import Optional as _Opt, List as _List, Union as _Union

class QuestionsRequest(_BM):
    complaint:          str
    complaint_en:       _Opt[str] = None
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
    questions:          list = []   # list of str or dict (with question_en)
    answers:            list = []
    demographics:       _Opt[dict] = None
    health_number:      _Opt[str] = None
    has_photo:          bool = False
    photo_count:        int = 0
    photo_base64:       _Opt[object] = None
    photo_mime:         _Opt[str] = None

class NextQuestionRequest(_BM):
    complaint:          str
    complaint_en:       _Opt[str] = None
    detected_language:  _Opt[str] = None
    previous_answers:   list = []
    demographics:       _Opt[dict] = None
    health_number:      _Opt[str] = None

class NextQuestionResponse(_BM):
    done:         bool
    question:     _Opt[dict] = None
    complaint_en: str

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
    ambulance_note:     _Opt[str] = None
    ambulance_total_eta: _Opt[int] = None  # total round-trip ETA (ambulance→patient→hospital)

# â”€â”€ helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _enrich_patient(p: dict) -> dict:
    """Merge queue record with health-DB demographics and medical records."""
    hn = p.get("health_number") or p.get("hn", "")

    # Extra fields stored by patient_app but not in DB schema
    # (they travel as JSON in the record dict but aren't persisted)
    db = get_patient(hn) if hn else None
    if db:
        p["first_name"]  = db.get("first_name", "")
        p["last_name"]   = db.get("last_name", "")
        p["sex"]         = db.get("sex", p.get("sex", "â€”"))
        p["blood_type"]  = db.get("blood_type", "?")
        p["nationality"] = db.get("nationality", "")
        p["flag"]        = NAT_FLAG.get(db.get("nationality", ""), "ðŸŒ")
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
                # â”€â”€ Server-side dedup â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
                # health_db may have duplicate rows if seed ran more than once
                # (diagnoses table has no UNIQUE constraint on health_number+icd_code)
                def _dedup(lst, key_fn):
                    seen, out = set(), []
                    for item in lst:
                        k = key_fn(item)
                        if k not in seen:
                            seen.add(k)
                            out.append(item)
                    return out

                # Diagnoses (medical history) â€” deduplicated by icd_code+description
                raw_diags = full_record.get("diagnoses", [])
                p["diagnoses"] = _dedup(
                    raw_diags,
                    lambda d: (d.get("icd_code") or "") + "|" + (d.get("description") or "")
                )

                # Active medications only â€” deduplicated by name+dosage
                all_meds = full_record.get("medications", [])
                active_meds = [m for m in all_meds if m.get("status") == "active"]
                p["medications"] = _dedup(
                    active_meds,
                    lambda m: (m.get("name") or "") + "|" + (m.get("dosage") or "")
                )

                # Latest vitals (most recent) - include bmi, glucose and full history
                vitals_list = full_record.get("vitals", [])
                if vitals_list:
                    latest = vitals_list[0]  # Already sorted by recorded_at DESC
                    bmi_val = latest.get("bmi")
                    if not bmi_val and db and db.get("weight_kg") and db.get("height_cm"):
                        try:
                            h_m = db["height_cm"] / 100
                            bmi_val = round(db["weight_kg"] / (h_m ** 2), 1)
                        except Exception:
                            bmi_val = None
                    p["vitals"] = {
                        "bp_systolic":  latest.get("bp_systolic"),
                        "bp_diastolic": latest.get("bp_diastolic"),
                        "heart_rate":   latest.get("heart_rate"),
                        "spo2":         latest.get("spo2"),
                        "temperature":  latest.get("temperature"),
                        "glucose":      latest.get("glucose"),
                        "bmi":          bmi_val,
                        "recorded_at":  latest.get("recorded_at"),
                    }
                    p["allVitals"] = _dedup(vitals_list[:10], lambda v: v.get("recorded_at", ""))
                else:
                    p["vitals"]    = {}
                    p["allVitals"] = []

                # Allergies - deduplicated by allergen name
                raw_allergy = full_record.get("allergies", [])
                p["allergies"] = _dedup(
                    raw_allergy,
                    lambda a: (a.get("allergen") or "").lower()
                )

                # Lab results (latest 15, deduplicated by test_name+test_date)
                raw_labs = full_record.get("lab_results", [])
                p["lab_results"] = _dedup(
                    raw_labs,
                    lambda l: (l.get("test_name") or "") + "|" + (l.get("test_date") or "")
                )[:15]

                # Past visits (latest 5, deduplicated by visit_date+chief_complaint)
                raw_visits = full_record.get("visits", [])
                p["visits"] = _dedup(
                    raw_visits,
                    lambda v: (v.get("visit_date") or "") + "|" + (v.get("chief_complaint") or v.get("diagnosis") or "")
                )[:5]

                # Doctor notes (latest 3) - critical for AI context and dashboard display
                raw_notes = full_record.get("doctor_notes", [])
                p["doctor_notes"] = _dedup(
                    raw_notes,
                    lambda n: (n.get("note_date") or "") + "|" + (n.get("assessment") or "")
                )[:3]

                # Imaging & diagnostics (latest 5)
                raw_imaging = full_record.get("imaging", [])
                p["imaging"] = _dedup(
                    raw_imaging,
                    lambda i: (i.get("study_date") or "") + "|" + (i.get("modality") or "") + "|" + (i.get("body_region") or "")
                )[:5]

                # Surgical history (latest 5)
                raw_surgeries = full_record.get("surgeries", [])
                p["surgeries"] = _dedup(
                    raw_surgeries,
                    lambda s: (s.get("surgery_date") or "") + "|" + (s.get("procedure_name") or "")
                )[:5]

                # Specialist consultations (latest 5)
                raw_consults = full_record.get("consultations", [])
                p["consultations"] = _dedup(
                    raw_consults,
                    lambda c: (c.get("consult_date") or "") + "|" + (c.get("specialty") or "")
                )[:5]

                # Upcoming / recent appointments (latest 3)
                raw_appts = full_record.get("appointments", [])
                p["appointments"] = _dedup(
                    raw_appts,
                    lambda a: (a.get("appointment_date") or "") + "|" + (a.get("department") or "")
                )[:3]
        except Exception as e:
            logger.error("Health record enrich FAILED for %s: %s", hn, e, exc_info=True)
            p["diagnoses"]      = []
            p["medications"]    = []
            p["vitals"]         = {}
            p["allVitals"]      = []
            p["allergies"]      = []
            p["lab_results"]    = []
            p["visits"]         = []
            p["doctor_notes"]   = []
            p["imaging"]        = []
            p["surgeries"]      = []
            p["consultations"]  = []
            p["appointments"]   = []
    else:
        # No health_number â€” use patient_id but keep visit-specific data from DB
        p["full_name"]   = p.get("patient_id", "Unknown Patient")
        p["flag"]        = "ðŸŒ"
        p["nationality"] = ""
        p["age"]         = p.get("age_range", "â€”")
        p["sex"]         = p.get("sex", "â€”")
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
        p["eta_display"] = "â€”"

    # Location
    p["location"] = {
        "lat": p.pop("location_lat", None),
        "lon": p.pop("location_lon", None),
    }

    # Illness media URLs â€” let dashboard know which indices exist
    pid = p.get("patient_id", "")
    photo_count = int(p.get("photo_count") or 0)
    if photo_count > 0 and pid:
        media_urls = []
        ILLNESS_EXTS = [".jpg", ".jpeg", ".png", ".webp", ".gif", ".mp4", ".webm", ".mov"]
        for idx in range(photo_count):
            for ext in ILLNESS_EXTS:
                candidate = ILLNESS_PHOTOS_DIR / f"{pid}_{idx}{ext}"
                if candidate.exists():
                    media_urls.append(f"/api/illness_photo/{pid}/{idx}")
                    break
        p["illness_media_urls"] = media_urls
    else:
        p["illness_media_urls"] = []

    # Patient profile photo flag (profile picture from health DB)
    hn = p.get("health_number", "")
    if hn:
        has_profile = any(
            (PATIENT_PHOTOS_DIR / f"{hn}{ext}").exists()
            for ext in (".png", ".jpg", ".jpeg", ".webp")
        )
        p["has_profile_photo"] = has_profile
        p["profile_photo_url"] = f"/api/patient_photo/{hn}" if has_profile else None
    else:
        p["has_profile_photo"] = False
        p["profile_photo_url"] = None

    return p


# â”€â”€ API endpoints â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@app.get("/api/stats")
def api_stats():
    """KPI bar data."""
    stats = hq.get_queue_stats()
    sts   = stats.get("by_status", {})

    # Active = incoming + arrived (both are "on their way / at the door")
    incoming_count = sts.get("incoming", 0)
    arrived_count  = sts.get("arrived", 0)
    en_route = incoming_count + arrived_count

    # Count triage levels — ONLY incoming (en-route) patients
    # so the chip badges match exactly what's shown in the patient list.
    # get_all_patients() already normalises ROUTINE → STANDARD on read,
    # so we count against the canonical MTS 5-level names.
    incoming_pts = [
        p for p in hq.get_all_patients(limit=500)
        if (p.get("status") or "incoming") == "incoming"
    ]
    from collections import Counter
    triage_counts = Counter(p.get("triage_level", "STANDARD") for p in incoming_pts)

    # Build the full 5-level dict the dashboard chip row expects
    by_triage_level = {
        "IMMEDIATE": triage_counts.get("IMMEDIATE", 0),
        "EMERGENCY": triage_counts.get(TRIAGE_EMERGENCY, 0),
        "URGENT":    triage_counts.get(TRIAGE_URGENT, 0),
        "STANDARD":  triage_counts.get("STANDARD", 0) + triage_counts.get(TRIAGE_ROUTINE, 0),
        "NON_URGENT": triage_counts.get("NON_URGENT", 0),
    }

    return {
        "total":           sum(sts.values()),
        "incoming":        incoming_count,
        # Legacy scalar fields kept for backward-compat with older dashboards
        "emergencies":     by_triage_level["EMERGENCY"],
        "urgents":         by_triage_level["URGENT"],
        "routines":        by_triage_level["STANDARD"],  # STANDARD is the new ROUTINE
        "en_route":        en_route,
        "treated":         sts.get("discharged", 0),
        "in_treatment":    sts.get("in_treatment", 0),
        # New: full 5-level breakdown for MTS chip row
        "by_triage_level": by_triage_level,
    }


@app.get("/api/patients")
def api_patients(sort: str = "triage", limit: int = 50, status: str = None):
    """Patient list, enriched with health DB data.

    If status is provided (e.g. 'discharged', 'in_treatment', 'arrived', 'incoming'),
    returns all patients matching that status using get_all_patients().
    Otherwise returns only incoming patients (default behaviour).
    """
    if status == "all":
        patients = hq.get_all_patients(limit=limit)
    elif status and status not in ("incoming", "en_route"):
        all_pts = hq.get_all_patients(limit=limit)
        patients = [p for p in all_pts if (p.get("status") or "").lower() == status.lower()]
    else:
        # Default: show both incoming (en-route) AND arrived (at the door, awaiting treatment)
        all_pts = hq.get_all_patients(limit=limit)
        patients = [p for p in all_pts if (p.get("status") or "incoming") in ("incoming", "arrived")]
    enriched = [_enrich_patient(p) for p in patients]

    if sort == "eta":
        enriched.sort(key=lambda p: p.get("eta_minutes") or 9999)
    elif sort == "risk":
        enriched.sort(key=lambda p: p.get("risk_score", 0) or 0, reverse=True)
    elif sort == "newest":
        enriched.sort(key=lambda p: p.get("timestamp", ""), reverse=True)
    elif sort == "oldest":
        enriched.sort(key=lambda p: p.get("timestamp", ""))
    # default: triage (already ordered by DB query)

    return enriched


@app.get("/api/tracking")
def api_tracking():
    """Live tracking data for active patients."""
    patients = hq.get_incoming_patients(limit=200)
    enriched = [_enrich_patient(p) for p in patients]
    # Return all incoming patients; dashboard will filter those with location data
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
            dist = maps._haversine_distance(lat, lon, h["lat"], h["lon"])
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

@app.get("/api/config/maps-key")
async def get_maps_key():
    import os
    key = os.getenv("MAPS_SUBSCRIPTION_KEY")
    return {"key": key}

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

    # Enrich â€” mirrors Streamlit _do_notify() record enrichment
    # Prefer server-translated `_qa_pairs` (English) if present in the assessment dict,
    # otherwise fallback to `body.answers`. This bypasses browser JS caching.
    raw_answers = body.assessment.get("_qa_pairs", body.answers or [])

    qa = []
    for a in raw_answers:
        if isinstance(a, dict):
            qa.append({
                "question":        a.get("question", ""),
                "question_en":     a.get("question_en", a.get("question", "")),  # English version
                "answer":          a.get("answer", ""),
                "original_answer": a.get("original_answer", a.get("originalAnswer", "")),
            })
        elif hasattr(a, "question"):
            qa.append({
                "question":        a.question,
                "question_en":     getattr(a, "question_en", a.question),
                "answer":          a.answer,
                "original_answer": getattr(a, "original_answer", None) or getattr(a, "answer", ""),
            })

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
        # assessment text: try multiple possible key names from different GPT response formats
        asmt_text = (
            asmt_obj.get("assessment") or
            asmt_obj.get("summary") or
            asmt_obj.get("clinical_summary") or
            asmt_obj.get("text") or
            asmt_obj.get("description") or
            ""
        )
        # If still no text, synthesize from conditions + recommended_action
        if not asmt_text and (asmt_obj.get("suspected_conditions") or asmt_obj.get("recommended_action")):
            conds = asmt_obj.get("suspected_conditions", [])
            rec   = asmt_obj.get("recommended_action", "")
            level = asmt_obj.get("triage_level", "")
            parts = []
            if level:   parts.append(f"Triage: {level}.")
            if conds:   parts.append(f"Suspected: {', '.join(conds) if isinstance(conds, list) else conds}.")
            if rec:     parts.append(f"Action: {rec}")
            asmt_text = " ".join(parts)

        if asmt_text and not record.get("assessment"):
            record["assessment"] = asmt_text
            
        # If it's a dict, store the entire dict to preserve clinical_report
        # so the dashboard can read assessment.clinical_report
        if asmt_obj:
            record["assessment"] = asmt_obj
            
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
        if asmt_obj.get("do_list"):
            record["do_list"] = asmt_obj["do_list"]
        if asmt_obj.get("dont_list"):
            record["dont_list"] = asmt_obj["dont_list"]

        logger.info(
            "Assessment flattened: level=%s score=%s conds=%s asmt=%s",
            record.get("triage_level"),
            record.get("risk_score"),
            str(record.get("suspected_conditions", []))[:60],
            str(record.get("assessment", ""))[:60],
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
            logger.info("Saved media %d (%s) â†’ %s", idx_m, kind, pid)
        except Exception as exc:
            logger.warning("Media %d save failed for %s: %s", idx_m, pid, exc)

    hq.add_patient(record)

    # Store ambulance dispatch note and update ETA to round-trip total
    if body.ambulance_note and body.ambulance_note.strip():
        hq.set_dispatch_note(record["patient_id"], body.ambulance_note.strip())
    if body.ambulance_total_eta and body.ambulance_total_eta > 0:
        # Replace GPS driving time with the full ambulance round-trip ETA so the
        # dashboard arrival timer reflects the real expected arrival time.
        hq.update_eta(record["patient_id"], int(body.ambulance_total_eta))

    logger.info(
        "Patient submitted: %s â†’ %s (lang=%s consent=%s ambulance=%s)",
        record["patient_id"], hospital.get("name", ""),
        body.detected_language, body.data_consent,
        bool(body.ambulance_note),
    )

    return {"ok": True, "patient_id": record["patient_id"]}


@app.post("/api/patient/transcribe")
async def patient_transcribe(audio: UploadFile = File(...), lang: str = Form(default="")):
    """Transcribe patient audio (WebM/Opus from browser) â†’ text.

    Pipeline:
      1. Azure Speech SDK  (via src.speech_handler if available)
         - Uses ``lang`` directly when provided (skips auto-detection → more accurate)
      2. OpenAI Whisper API (if OPENAI_API_KEY is set)
      3. Return empty â†’ frontend falls back to Web Speech / manual typing
    """
    import os as _os, tempfile as _tmp

    raw = await audio.read()

    suffix = ".webm"
    if audio.filename:
        ext = _os.path.splitext(audio.filename)[1].lower()
        if ext in (".webm", ".ogg", ".mp4", ".wav", ".m4a"):
            suffix = ext

    # â”€â”€ 1. Try Azure Speech SDK â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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
                    # Use the patient's selected language directly when available;
                    # skip auto-detection which can fail on short/accented speech.
                    result = speech.recognize_from_audio_file(wav_path, language=lang or None)
                    try:
                        _os.unlink(wav_path)
                    except Exception:
                        pass
                    if result and result.get("text", "").strip():
                        logger.info("Transcribed via Azure Speech (lang=%s): %sâ€¦", lang or "auto", result["text"][:60])
                        return {"text": result["text"], "language": result.get("language", lang or "en-US")}
                    else:
                        logger.warning("Azure Speech returned no text â€ falling back to Whisper")
                else:
                    logger.warning("Audio conversion failed (ffmpeg/pydub missing?) â€” falling back to Whisper")
            else:
                logger.warning("Azure Speech not initialized (check SPEECH_KEY/SPEECH_REGION) â€” falling back to Whisper")
        except ImportError:
            logger.warning("src.speech_handler not found â€” falling back to Whisper")
        except Exception as e:
            logger.warning("Azure Speech failed: %s â€” falling back to Whisper", e)
    else:
        logger.info("SPEECH_KEY not set â€” skipping Azure Speech, trying Whisper")

    # â”€â”€ 2. OpenAI Whisper API â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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
                logger.info("Transcribed via Whisper: %sâ€¦ (lang=%s)", text[:60], lang)
                return {"text": text.strip(), "language": lang_bcp47}
            else:
                logger.warning("Whisper returned empty text")
        except Exception as e:
            logger.warning("Whisper transcription failed: %s", e)
    else:
        logger.warning("OPENAI_API_KEY not set â€” Whisper unavailable")

    # â”€â”€ 3. Nothing worked â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    logger.info("All server transcription methods failed â€” frontend will use Web Speech")
    return {"text": "", "language": "en-US"}


@app.post("/api/patient/questions", response_model=QuestionsResponse)
def patient_questions(body: QuestionsRequest):
    """Translate complaint to English via Azure Translator, then generate
    GPT-4 clinical follow-up questions via TriageEngine.

    This mirrors the Streamlit flow:
      _do_process(): Azure Translator.translate_to_english()
      page_photos â†’ _go_to_questions(): TriageEngine.generate_questions()
    """
    triage, translator = _get_triage_engine()

    # â”€â”€ Step 1: Translate complaint to English (Azure Translator / GPT fallback) â”€â”€â”€â”€â”€
    complaint_en = body.complaint_en or body.complaint
    lang_hint = body.detected_language or "en-US"

    if not body.complaint_en and not lang_hint.lower().startswith("en"):
        if translator:
            try:
                # Pass detected language as source to improve translation accuracy
                result = translator.translate_to_english(
                    body.complaint,
                    source_language=body.detected_language,
                )
                if result:
                    complaint_en = result
                    logger.info("Complaint translated from %s to EN: '%sâ€¦'", body.detected_language or "auto", complaint_en[:60])
            except Exception as exc:
                logger.warning("Translation failed (%s) â€” using original text.", exc)
        else:
            # Fallback: use GPT to translate the complaint to English
            openai_key = __import__("os").getenv("OPENAI_API_KEY", "")
            if openai_key and body.complaint.strip():
                try:
                    import openai as _oai
                    _client = _oai.OpenAI(api_key=openai_key)
                    _resp = _client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[{
                            "role": "system",
                            "content": "Translate the user's text to English. Reply with ONLY the translated text, nothing else."
                        }, {
                            "role": "user",
                            "content": body.complaint
                        }],
                        max_tokens=250,
                        temperature=0,
                    )
                    _translated = _resp.choices[0].message.content.strip()
                    if _translated:
                        complaint_en = _translated
                        logger.info("Complaint (GPT-translated) from auto to EN: '%sâ€¦'", complaint_en[:60])
                except Exception as exc:
                    logger.warning("GPT complaint translation failed (%s) â€” using original.", exc)

    # â”€â”€ Step 2: Generate GPT-4 clinical questions â€” ALWAYS in English first â”€â”€
    # English questions are the ground truth (question_en), then translated for the patient.
    # Do NOT inject language into GPT prompt â€” generate clean English questions,
    # then translate them in Step 3 so the dashboard always has question_en available.
    lang_hint  = body.detected_language or "en-US"
    _lang_map  = {
        "tr": "Turkish", "de": "German",  "fr": "French",
        "es": "Spanish", "ar": "Arabic",  "nl": "Dutch",
        "it": "Italian", "pl": "Polish",  "pt": "Portuguese",
        "ru": "Russian", "zh": "Chinese",
    }
    lang_name = next((v for k, v in _lang_map.items() if lang_hint.lower().startswith(k)), None)

    questions = triage.generate_questions(chief_complaint=complaint_en)
    logger.info("Generated %d questions (lang=%s): '%sâ€¦'", len(questions), lang_hint, complaint_en[:50])

    # Step 2b: Tag each question with its English original before any translation
    for q in questions:
        q["question_en"] = q.get("question", "")   # Always preserve English version

    # â”€â”€ Step 3: Translate questions/options into patient's language â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    if lang_name and not lang_hint.lower().startswith("en"):
        # Try Azure Translator first, fall back to GPT inject on individual questions
        if translator:
            for q in questions:
                q_text = q.get("question", "")
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
                            translated_opt = translator.translate_from_english(opt, body.detected_language)
                            translated_opts.append(translated_opt if translated_opt else opt)
                        except Exception:
                            translated_opts.append(opt)
                    q["options"] = translated_opts
        else:
            # No Azure Translator: re-generate questions with language injection
            # but keep question_en already set above
            gpt_complaint_lang = (
                f"[IMPORTANT: Generate ALL questions and ALL answer options ENTIRELY in {lang_name}. "
                f"Do not use English. Patient language: {lang_name}.] "
                f"{complaint_en}"
            )
            translated_questions = triage.generate_questions(chief_complaint=gpt_complaint_lang)
            # Merge: keep question_en from English run, take question/options from translated run
            for i, q in enumerate(questions):
                if i < len(translated_questions):
                    q["question"] = translated_questions[i].get("question", q["question"])
                    if "options" in translated_questions[i]:
                        q["options"] = translated_questions[i]["options"]

    return QuestionsResponse(questions=questions, complaint_en=complaint_en)


@app.post("/api/patient/questions/next", response_model=NextQuestionResponse)
def patient_questions_next(body: NextQuestionRequest):
    """
    V10 Feature: Step-by-step adaptive questioning with Medical History and Vision support.
    """
    triage, translator = _get_triage_engine()

    complaint_en = body.complaint_en or body.complaint
    lang_hint = body.detected_language or "en-US"

    _lang_map  = {
        "tr": "Turkish", "de": "German",  "fr": "French",
        "es": "Spanish", "ar": "Arabic",  "nl": "Dutch",
        "it": "Italian", "pl": "Polish",  "pt": "Portuguese",
        "ru": "Russian", "zh": "Chinese",
    }
    lang_name = next((v for k, v in _lang_map.items() if lang_hint.lower().startswith(k)), None)

    # 1. Translate answers to English
    qa_pairs = []
    for item in body.previous_answers:
        q_en = item.get("question_en", item.get("question", ""))
        q_orig = item.get("question", "")
        ans = item.get("answer", "")
        img = item.get("image", None)

        ans_en = str(ans)
        if ans and lang_hint and not lang_hint.lower().startswith("en"):
            if translator:
                try:
                    translated = translator.translate_to_english(str(ans), source_language=lang_hint)
                    if translated: ans_en = translated
                except:
                    pass

        qa_pairs.append({
            "question": q_en,
            "question_orig": q_orig,
            "answer": ans_en,
            "original_answer": str(ans),
            "image": img
        })

    # 2. Get medical history if provided
    medical_history = None
    if body.health_number:
        medical_history = get_full_record(body.health_number)

    # 3. Generate Next Question
    result = triage.generate_next_question(
        chief_complaint=complaint_en,
        previous_answers=qa_pairs,
        demographics=body.demographics,
        medical_history=medical_history
    )

    is_done = result.get("done", False)
    q = result.get("question", None)

    if q:
        q["question_en"] = q.get("question", "")
        if lang_name and not lang_hint.lower().startswith("en") and translator:
            try:
                translated_q = translator.translate_from_english(q["question"], lang_hint)
                if translated_q:
                    q["question"] = translated_q
            except Exception as e:
                logger.warning("Next question translation failed: %s", e)

            if "options" in q and q["options"]:
                translated_opts = []
                for opt in q["options"]:
                    try:
                        translated_opt = translator.translate_from_english(opt, lang_hint)
                        translated_opts.append(translated_opt if translated_opt else opt)
                    except:
                        translated_opts.append(opt)
                q["options"] = translated_opts

    return NextQuestionResponse(
        done=is_done,
        question=q,
        complaint_en=complaint_en
    )


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

    # â”€â”€ Step 1: Translate answers to English â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    qa_pairs = []

    # Build a question_en lookup from body.questions list (may contain dicts with question_en)
    q_en_lookup: dict = {}
    for i, bq in enumerate(body.questions or []):
        if isinstance(bq, dict):
            q_en_lookup[i] = bq.get("question_en") or bq.get("question") or ""
        else:
            q_en_lookup[i] = str(bq)

    for idx, item in enumerate(body.answers):
        if isinstance(item, dict):
            q_orig = item.get("question", "")
            # question_en: prefer explicit field, then look up from questions list, then keep q_orig
            q_en   = item.get("question_en") or q_en_lookup.get(idx, q_orig) or q_orig
            ans    = item.get("answer", item.get("original_answer", ""))
            ans_orig = item.get("original_answer", str(ans))
            img = item.get("image", None)
        else:
            continue

        if not ans:
            continue

        # Translate answer to English for accurate GPT-4 assessment
        ans_en = str(ans)
        if body.detected_language and not body.detected_language.startswith("en"):
            translated = None
            if translator:
                try:
                    translated = translator.translate_to_english(
                        str(ans),
                        source_language=body.detected_language,
                    )
                except Exception as exc:
                    logger.warning("Azure answer translation failed (%s). Falling back.", exc)

            if translated:
                ans_en = translated
            else:
                # Fallback: use GPT to translate short answer to English
                openai_key = __import__("os").getenv("OPENAI_API_KEY", "")
                if openai_key and str(ans).strip():
                    try:
                        import openai as _oai
                        _client = _oai.OpenAI(api_key=openai_key)
                        _resp = _client.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=[{
                                "role": "system",
                                "content": "Translate the user's text to English. Respond with ONLY the English translation, absolutely nothing else."
                            }, {
                                "role": "user",
                                "content": str(ans)
                            }],
                            max_tokens=60,
                            temperature=0,
                        )
                        _translated = _resp.choices[0].message.content.strip()
                        if _translated:
                            ans_en = _translated
                    except Exception as exc:
                        logger.warning("GPT answer translation failed (%s) â€” using original.", exc)

        qa_pairs.append({
            "question":        q_en,           # English question for GPT + dashboard
            "question_orig":   q_orig,         # Original language question
            "answer":          ans_en,         # English answer for GPT + dashboard
            "original_answer": ans_orig,       # Original language answer
        })

    logger.info(
        "Assessing triage: complaint='%sâ€¦', %d Q&A pairs, lang=%s",
        complaint_en[:50], len(qa_pairs), body.detected_language or "en",
    )

    # â”€â”€ Step 2: GPT-4 triage assessment (TriageEngine) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    medical_history = None
    if getattr(body, "health_number", None):
        medical_history = get_full_record(body.health_number)

    assessment = triage.assess_triage(
        chief_complaint=complaint_en,
        answers=qa_pairs,
        medical_history=medical_history,
        language=body.detected_language or "en-US",
    )

    # â”€â”€ Step 3: Generate pre-arrival DO/DON'T advice (GPT-4 + RAG) â”€â”€â”€â”€
    advice = triage.generate_pre_arrival_advice(
        chief_complaint=complaint_en,
        assessment=assessment,
        language=body.detected_language or "en-US",
    )
    assessment["do_list"]   = advice.get("do_list",   [])
    assessment["dont_list"] = advice.get("dont_list", [])

    # Include qa_pairs in response so patient_app can forward them (with question_en) to submit
    assessment["_qa_pairs"] = qa_pairs

    logger.info(
        "Assessment done: level=%s score=%s do=%d dont=%d qa=%d",
        assessment.get("triage_level"),
        assessment.get("risk_score"),
        len(assessment["do_list"]),
        len(assessment["dont_list"]),
        len(qa_pairs),
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


@app.get("/api/patient/{patient_id}/status")
def api_patient_status(patient_id: str):
    """Return concise patient status and physician override info."""
    all_p = hq.get_all_patients(limit=200)
    match = next((p for p in all_p if p["patient_id"] == patient_id), None)
    if not match:
        raise HTTPException(404, "Patient not found")
    
    has_override = bool(match.get("override_action"))
    return {
        "patient_id": patient_id,
        "status": match.get("status"),
        "ai_triage_level": match.get("ai_triage_level") or match.get("triage_level"),
        "triage_level": match.get("triage_level"),
        "physician_decision": match.get("override_action") or None,
        "new_triage_level": match.get("triage_level") if has_override else None,
        "physician_note": match.get("override_note") or None,
        "override_timestamp": match.get("updated_at") if has_override else None,
    }


@app.get("/api/health_record/{health_number}")
def api_health_record(health_number: str):
    """Full health record from health DB."""
    rec = get_full_record(health_number)
    if not rec or not rec.get("patient"):
        raise HTTPException(404, "Health record not found")
    return rec


@app.patch("/api/patient/{patient_id}/status")
def api_update_status(patient_id: str, body: dict):
    """Update patient status (incoming â†’ arrived â†’ in_treatment â†’ discharged)."""
    status = body.get("status")
    valid  = {"incoming", "arrived", "in_treatment", "discharged"}
    if status not in valid:
        raise HTTPException(400, f"Invalid status. Must be one of: {valid}")
    ok = hq.update_status(patient_id, status)
    if not ok:
        raise HTTPException(500, "Failed to update status")
    return {"ok": True, "patient_id": patient_id, "status": status}


@app.patch("/api/patient/{patient_id}/triage")
def api_update_triage(patient_id: str, body: dict):
    """Override the AI triage level with a physician decision.

    Accepts all MTS 5-level values (IMMEDIATE, EMERGENCY, URGENT, STANDARD,
    NON_URGENT) plus legacy ROUTINE (normalised → STANDARD).
    For the APPROVE action, ``new_level`` is optional — the current patient
    level is used when omitted.
    """
    new_level = body.get("new_level")
    action    = body.get("action", "")
    note      = body.get("note", "")

    # APPROVE keeps the current triage level — resolve it from the DB
    if action == "APPROVE" and not new_level:
        all_p   = hq.get_all_patients(limit=200)
        patient = next((p for p in all_p if p["patient_id"] == patient_id), None)
        new_level = (patient or {}).get("triage_level") or "URGENT"

    # Normalise legacy alias
    if new_level == "ROUTINE":
        new_level = "STANDARD"

    valid = {"IMMEDIATE", "EMERGENCY", "URGENT", "STANDARD", "NON_URGENT"}
    if new_level not in valid:
        raise HTTPException(
            400,
            f"Invalid triage level '{new_level}'. Must be one of: {sorted(valid)}"
        )

    ok = hq.update_triage(patient_id, new_level, action, note)
    if not ok:
        raise HTTPException(500, "Failed to update triage level in database")

    return {
        "ok":             True,
        "patient_id":     patient_id,
        "triage_level":   new_level,
        "override_action": action,
        "override_note":  note,
    }


@app.patch("/api/patient/{patient_id}/location")
def api_update_location(patient_id: str, body: dict):
    """Update patient live tracking location and ETA."""
    lat = body.get("lat")
    lon = body.get("lon")
    eta_minutes = body.get("eta_minutes")
    
    # If ETA is missing from the client, we can try to recalculate it using maps handler
    if eta_minutes is None and lat is not None and lon is not None:
        try:
            # We fetch the patient to find their destination hospital
            all_p = hq.get_all_patients(limit=200)
            patient_record = next((p for p in all_p if p["patient_id"] == patient_id), None)
            
            if patient_record and patient_record.get("destination_hospital"):
                maps = _get_maps()
                # Recalculate ETA dynamically using your MapsHandler (assumes standard structure)
                hospitals = maps.find_nearest_hospitals(lat, lon, count=20) 
                for h in hospitals:
                    if h["name"] == patient_record["destination_hospital"]:
                        eta_minutes = h["eta_minutes"]
                        break
        except Exception as e:
            logger.warning("Dynamic ETA calculation failed: %s", e)

    if lat is None or lon is None:
        raise HTTPException(400, "Missing lat or lon")
        
    ok = hq.update_location(patient_id, lat, lon, eta_minutes)
    
    if not ok:
        raise HTTPException(500, "Failed to update location in database")
        
    return {
        "ok": True, 
        "patient_id": patient_id, 
        "lat": lat, 
        "lon": lon, 
        "eta_minutes": eta_minutes
    }


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
    """Serve illness media â€” images and videos."""
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

@app.get("/api/hospitals/all")
def api_all_hospitals():
    """Return all static hospitals to display as background markers on the map."""
    try:
        from src.maps_handler import ALL_HOSPITALS
        return ALL_HOSPITALS
    except ImportError:
        return []

@app.post("/api/admin/clear")
def api_clear():
    """Clear all patients (testing only)."""
    hq.clear_queue()
    return {"ok": True}


@app.post("/api/admin/seed")
def api_seed():
    """Seed realistic test patients dynamically."""
    import random
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    
    # Pool of valid non-Turkish health numbers (DE and UK only)
    health_numbers_de = [f"DEMO-DE-{i:03d}" for i in range(1, 11)]
    health_numbers_uk = [f"DEMO-UK-{i:03d}" for i in range(1, 11)]
    all_hn = health_numbers_de + health_numbers_uk
    
    templates = [
        {"triage_level": "EMERGENCY", "chief_complaint": "Crushing chest pain radiating to left arm", "assessment": "Suspected STEMI. Immediate cath lab activation required. Patient diaphoretic, BP 85/50.", "red_flags": ["chest_pain_radiation", "diaphoresis", "hypotension"], "risk_score": 10, "suspected_conditions": ["STEMI", "ACS"], "recommended_action": "Activate cath lab. 12-lead ECG. Aspirin 300mg. IV access x2.", "time_sensitivity": "Within 5 minutes", "language": "de-DE", "complaint_text": "Starke Brustschmerzen die in den linken Arm ausstrahlen", "qa_transcript": [{"question": "Wann hat es begonnen?", "question_en": "When did it start?", "answer": "15 minutes ago", "original_answer": "Vor 15 Minuten"}, {"question": "SchmerzstÃ¤rke 1-10?", "question_en": "Rate pain 1-10?", "answer": "9", "original_answer": "9"}, {"question": "Kurzatmigkeit?", "question_en": "Any shortness of breath?", "answer": "Yes", "original_answer": "Ja, sehr"}], "has_photo": False, "photo_count": 0},
        {"triage_level": "EMERGENCY", "chief_complaint": "Thunderclap headache, worst of life, sudden onset", "assessment": "Possible subarachnoid hemorrhage. Immediate CT head required. GCS 14.", "red_flags": ["sudden_severe_headache", "vomiting", "photophobia", "neck_stiffness"], "risk_score": 9, "suspected_conditions": ["Subarachnoid Hemorrhage", "Meningitis"], "recommended_action": "Immediate CT head non-contrast. Lumbar puncture if CT negative.", "time_sensitivity": "Within 10 minutes", "language": "en-GB", "complaint_text": "Worst headache of my life, came out of nowhere", "qa_transcript": [{"question": "When did it start?", "question_en": "When did it start?", "answer": "Suddenly 20 min ago", "original_answer": "Suddenly 20 min ago"}, {"question": "Any visual changes?", "question_en": "Any visual changes?", "answer": "Yes, blurry", "original_answer": "Yes, blurry"}], "has_photo": True, "photo_count": 1},
        {"triage_level": "URGENT", "chief_complaint": "Severe abdominal pain after blunt trauma", "assessment": "Blunt abdominal trauma. Possible splenic laceration. Rigid board-like abdomen.", "red_flags": ["rigid_abdomen", "post_trauma", "tachycardia"], "risk_score": 8, "suspected_conditions": ["Splenic Laceration", "Internal Bleeding"], "recommended_action": "FAST ultrasound. Trauma surgery consult. 2x large bore IV. Cross-match.", "time_sensitivity": "Within 30 minutes", "language": "en-GB", "complaint_text": "Really bad stomach pain after being hit by a car door", "qa_transcript": [{"question": "Where is the pain?", "question_en": "Where is the pain?", "answer": "Left abdomen", "original_answer": "Left abdomen"}, {"question": "Rate pain 1-10?", "question_en": "Rate pain 1-10?", "answer": "8", "original_answer": "8"}], "has_photo": True, "photo_count": 2},
        {"triage_level": "URGENT", "chief_complaint": "Acute asthma exacerbation, difficulty breathing", "assessment": "Moderate asthma exacerbation. SpO2 91% on air. Audible wheeze bilateral.", "red_flags": ["low_spo2", "respiratory_distress"], "risk_score": 7, "suspected_conditions": ["Asthma Exacerbation", "COPD"], "recommended_action": "Nebulised salbutamol 5mg. Oral prednisolone 40mg. O2 titrate to 94-98%.", "time_sensitivity": "Within 20 minutes", "language": "de-DE", "complaint_text": "Ich bekomme sehr schwer Luft, meine Lungen fühlen sich eng an", "qa_transcript": [{"question": "Haben Sie ein Inhalatorspray?", "question_en": "Do you have an inhaler?", "answer": "Yes but not helping", "original_answer": "Ja, aber es hilft nicht"}, {"question": "Seit wann?", "question_en": "How long?", "answer": "1 hour", "original_answer": "Seit 1 Stunde"}], "has_photo": False, "photo_count": 0},
        {"triage_level": "ROUTINE", "chief_complaint": "Mild headache and dizziness since this morning", "assessment": "Likely tension headache with mild dehydration. No neurological signs. BP normal.", "red_flags": [], "risk_score": 2, "suspected_conditions": ["Tension Headache", "Dehydration"], "recommended_action": "Oral hydration. Paracetamol 1g. Reassess in 1 hour.", "time_sensitivity": "Within 2 hours", "language": "de-DE", "complaint_text": "Leichte Kopfschmerzen und Schwindel seit dem Morgen", "qa_transcript": [{"question": "Wie lange schon?", "question_en": "How long?", "answer": "Since morning", "original_answer": "Seit dem Morgen"}, {"question": "Fieber?", "question_en": "Any fever?", "answer": "No", "original_answer": "Nein"}], "has_photo": False, "photo_count": 0},
        {"triage_level": "ROUTINE", "chief_complaint": "Twisted ankle during a run, mild swelling", "assessment": "Ankle sprain. Ottawa rules negative. RICE protocol advised.", "red_flags": [], "risk_score": 3, "suspected_conditions": ["Ankle Sprain"], "recommended_action": "X-ray if weight bearing is impossible. RICE.", "time_sensitivity": "Within 3 hours", "language": "en-GB", "complaint_text": "Twisted my ankle during a morning run, it's slightly swollen now", "qa_transcript": [{"question": "Can you walk on it?", "question_en": "Can you walk on it?", "answer": "Yes, but it hurts", "original_answer": "Yes, but it hurts"}], "has_photo": True, "photo_count": 1},
        {"triage_level": "URGENT", "chief_complaint": "High fever, productive cough, feeling very weak", "assessment": "Suspected lobar pneumonia. SpO2 93%. Needs chest X-ray and antibiotics.", "red_flags": ["high_fever", "tachypnea"], "risk_score": 6, "suspected_conditions": ["Pneumonia", "Sepsis screen"], "recommended_action": "Chest X-ray. Blood cultures. IV Co-amoxiclav.", "time_sensitivity": "Within 1 hour", "language": "de-DE", "complaint_text": "Hohes Fieber und produktiver Husten, fühle mich sehr schwach", "qa_transcript": [{"question": "Wie hoch ist das Fieber?", "question_en": "How high is the fever?", "answer": "39.5 C", "original_answer": "39,5 C"}], "has_photo": False, "photo_count": 0}
    ]
    
    # Pick a random number between 2 and 4 patients to seed each time
    num_to_seed = random.randint(2, 4)
    selected_templates = random.sample(templates, k=num_to_seed)
    
    import time
    seeded_count = 0
    for tmpl in selected_templates:
        # Clone the template so we can mutate it
        pt = dict(tmpl)
        # Timestamp + random suffix = always unique, never collides
        unique_suffix = f"{int(time.time() * 1000) % 100000:05d}{random.randint(10, 99)}"
        pt["patient_id"] = f"ER-{unique_suffix}"
        import time as _t; _t.sleep(0.002)  # tiny gap so timestamps differ
        
        # Assign a random valid health number matching the template's language
        if pt["language"] == "de-DE":
            pt["health_number"] = random.choice(health_numbers_de)
        else:
            pt["health_number"] = random.choice(health_numbers_uk)

        # Randomize geolocation around Ulm (~48.4, 9.9) within roughly +/- 15km
        pt["location"] = {"lat": 48.4 + random.uniform(-0.15, 0.15), "lon": 9.9 + random.uniform(-0.15, 0.15)}
        pt["destination_hospital"] = "Ulm Uni Klinik"
        # Derive ETA from actual distance to hospital (60 km/h)
        loc = pt.get("location", {})
        _dlat = HOSPITAL_LAT - loc.get("lat", HOSPITAL_LAT)
        _dlon = HOSPITAL_LON - loc.get("lon", HOSPITAL_LON)
        _dist_km = _math.sqrt((_dlat * 111.0) ** 2 + (_dlon * 72.0) ** 2)
        pt["eta_minutes"] = max(1, round(_dist_km / 1.0))  # 1 km/min = 60 km/h
        pt["data_consent"] = True
        pt["timestamp"] = now
        
        hq.add_patient(pt)
        seeded_count += 1
        
    return {"ok": True, "seeded": seeded_count}




@app.get("/api/debug/health_db")
def debug_health_db():
    """Debug: show health_records.db status. Visit /api/debug/health in browser."""
    try:
        from src.health_db_v1 import _conn as hdb_conn, DB_PATH as HDB_PATH
        import sqlite3
        import os
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
            "status": "OK" if vitals > 0 and diags > 0 else "NEEDS_RESEED â€” call POST /api/admin/reseed_health",
        }
    except Exception as e:
        return {"error": str(e), "status": "ERROR"}

@app.post("/api/debug/health_db/reset")
def reset_health_db():
    """Force re-seed vitals/diagnoses/medications if they were empty."""
    try:
        from src.health_db_v1 import _conn as hdb_conn, _seed as hdb_seed
        with hdb_conn() as con:
            for tbl in ("vitals","diagnoses","medications","lab_results","allergies","visits"):
                con.execute(f"DELETE FROM {tbl}")
            hdb_seed(con)
        return {"ok": True, "message": "Health records re-seeded"}
    except Exception as e:
        raise HTTPException(500, f"Re-seed failed: {e}")

# â”€â”€ Serve the dashboard HTML â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@app.get("/", response_class=HTMLResponse)
def serve_dashboard():
    path = ROOT / "ui" / "hospital_dashboard_v9.html"
    if path.exists():
        return HTMLResponse(path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Dashboard HTML not found</h1>", status_code=404)


@app.get("/patient", response_class=HTMLResponse)
def serve_patient_app():
    path = ROOT / "ui" / "patient_app_v13.html"
    if path.exists():
        return HTMLResponse(path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Patient app HTML not found</h1>", status_code=404)


@app.get("/patient_app_13.html", response_class=HTMLResponse)
def serve_patient_app_plain():
    """Direct filename access — convenience alias."""
    return serve_patient_app()


@app.get("/patient_app_v13.html", response_class=HTMLResponse)
def serve_patient_app_v13():
    """Direct filename access — convenience alias."""
    return serve_patient_app()


@app.get("/docs/images/{filename}")
def serve_docs_image(filename: str):
    """Serve logo and docs images (needed when HTML is loaded via server, not <file://>)."""
    from fastapi.responses import Response as _Resp
    img_path = ROOT / "docs" / "images" / filename
    if not img_path.exists():
        raise HTTPException(404, f"Image not found: {filename}")
    ext = img_path.suffix.lower()
    mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
            "gif": "image/gif", "svg": "image/svg+xml", "webp": "image/webp"}.get(ext.lstrip("."), "application/octet-stream")
    return _Resp(img_path.read_bytes(), media_type=mime, headers={"Cache-Control": "max-age=3600"})

# ————————————————————————————————————————————————————————————————————————————————
# PATIENT APP APIs
# ————————————————————————————————————————————————————————————————————————————————

# Lazy-init services (only when first patient API call arrives)
_patient_services: dict = {}

@app.get("/api/ai-status")
def api_ai_status():
    """Expose AI engine initialization state and deployment validity.
    Called by the frontend on load to detect mock/real mode and surface
    configuration errors (wrong deployment name, bad API key, etc.)."""
    import os as _os
    azure_key  = bool(_os.getenv("AZURE_OPENAI_KEY", "").strip()) and _os.getenv("AZURE_OPENAI_KEY") != "your-key"
    azure_ep   = bool(_os.getenv("AZURE_OPENAI_ENDPOINT", "").strip())
    openai_key = bool(_os.getenv("OPENAI_API_KEY", "").strip()) and _os.getenv("OPENAI_API_KEY") != "your-key"
    deployment = _os.getenv("GPT_DEPLOYMENT", "gpt-4")

    init_error = ""
    if "triage" in _patient_services:
        engine = _patient_services["triage"]
        initialized = engine._initialized
        model = engine.deployment if initialized else deployment
        init_error = getattr(engine, "_init_error", "")
    else:
        initialized = (azure_key and azure_ep) or openai_key
        model = deployment

    if not initialized and not init_error:
        if not azure_key and not openai_key:
            init_error = "No API keys found. Set AZURE_OPENAI_KEY or OPENAI_API_KEY in .env."
        elif azure_key and azure_ep and not init_error:
            init_error = (
                f"Azure credentials present but engine not yet started, or deployment "
                f"'{deployment}' failed validation. Check server logs."
            )

    return {
        "ai_initialized": initialized,
        "model": model,
        "mode": "real" if initialized else "mock",
        "azure_configured": azure_key and azure_ep,
        "openai_configured": openai_key,
        "deployment": deployment,
        "error": init_error or None,
        "warning": (
            f"Running in MOCK mode — {init_error}" if not initialized and init_error
            else ("Running in MOCK mode — no AI credentials configured." if not initialized else None)
        ),
    }


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


# â”€â”€ Entry point â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
if __name__ == "__main__":
    import os as _os_check, shutil

    speech_key  = _os_check.getenv("SPEECH_KEY", "")
    openai_key  = _os_check.getenv("OPENAI_API_KEY", "")
    # shutil.which can miss ffmpeg on Windows venvs â€” verify with subprocess
    try:
        import subprocess as _sp
        _sp.run(["ffmpeg", "-version"], capture_output=True, timeout=5, check=True)
        ffmpeg_ok = True
    except Exception:
        ffmpeg_ok = False
    _migrate_queue_db()

    _move_thread = _threading.Thread(target=_move_patients_loop, daemon=True, name="PatientMovement")
    _move_thread.start()
    logger.info("Patient movement background thread started.")
    
    print("VitalNavAI ER Command Center running on http://localhost:8001")

    uvicorn.run(app, host="0.0.0.0", port=8001, reload=False, log_level="info")