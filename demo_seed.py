"""
Demo Seed — University Clinic Ulm
===================================
Populates the hospital queue with a realistic snapshot for demo/recording purposes.

Scenario:  A busy morning shift at Universitätsklinikum Ulm — 7 patients total.
  • 3  patients en route  (IMMEDIATE × 1, EMERGENCY × 1, URGENT × 1)
       — 2 by ambulance, 1 own transport  |  ETA 10–15 min each
  • 3  patients in treatment (all have doctors + beds assigned — no awaiting-count drift)
  • 1  patient discharged earlier today

Language mix: 2 Turkish · 2 German · 3 British

Run standalone:   python demo_seed.py
Or call via API:  POST /api/admin/demo
"""

from __future__ import annotations
import json
import math
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ── paths ──────────────────────────────────────────────────────────────────
ROOT     = Path(__file__).parent
DB_PATH  = ROOT / "patient_queue.db"   # matches src/hospital_queue.py → parent.parent / "patient_queue.db"

# ── University Clinic Ulm ──────────────────────────────────────────────────
HOSPITAL        = "Universitätsklinikum Ulm"
HOSPITAL_LAT    = 48.4215
HOSPITAL_LON    = 9.9593

# ── helpers ────────────────────────────────────────────────────────────────
def _eta(lat: float, lon: float) -> int:
    dlat  = HOSPITAL_LAT - lat
    dlon  = HOSPITAL_LON - lon
    dist  = math.sqrt((dlat * 111.0) ** 2 + (dlon * 72.0) ** 2)
    return max(2, round(dist / 1.0))   # ~60 km/h


def _ago(hours: float = 0, minutes: float = 0) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours, minutes=minutes)).isoformat()


# ── doctor roster ──────────────────────────────────────────────────────────
DOCTORS = [
    {
        "id": "DR001", "name": "Dr. Bernd Hoffman",
        "photo": "/doctor_photos/Dr.Bernd_Hoffman.png",
        "specialization": "Emergency Medicine", "department": "ER",
        "current_patients": 2, "max_patients": 8, "availability": "available",
        "skills": ["trauma", "cardiac", "pediatric"], "location": "ER Room 3",
        "response_time": 5, "shift": "08:00 - 18:00", "contact": "Ext. 4401", "experience": "12 yrs"
    },
    {
        "id": "DR002", "name": "Dr. Birgit Schmidt",
        "photo": "/doctor_photos/Dr.Birgit_Schmidt.png",
        "specialization": "Cardiology", "department": "Cardiology",
        "current_patients": 3, "max_patients": 6, "availability": "available",
        "skills": ["cardiac", "arrhythmia", "ICU"], "location": "Cardiology Ward C-2",
        "response_time": 6, "shift": "08:00 - 20:00", "contact": "Ext. 2210", "experience": "15 yrs"
    },
    {
        "id": "DR003", "name": "Dr. Britta Weidermann",
        "photo": "/doctor_photos/Dr.Britta_Weidermann.png",
        "specialization": "Emergency Medicine", "department": "ER",
        "current_patients": 0, "max_patients": 8, "availability": "available",
        "skills": ["general", "trauma", "respiratory"], "location": "ER Room 1",
        "response_time": 3, "shift": "06:00 - 16:00", "contact": "Ext. 4405", "experience": "8 yrs"
    },
    {
        "id": "DR004", "name": "Dr. Hasan Karatay",
        "photo": "/doctor_photos/Dr.Hasan_Karatay.png",
        "specialization": "Neurology", "department": "Neurology",
        "current_patients": 2, "max_patients": 5, "availability": "available",
        "skills": ["stroke", "epilepsy", "neuro-ICU"], "location": "Neurology Ward N-3",
        "response_time": 4, "shift": "10:00 - 22:00", "contact": "Ext. 5100", "experience": "5 yrs"
    },
]

# ── beds (30 beds across 5 departments) ────────────────────────────────────
BEDS = [
    # ICU
    {"id": "ICU-101", "type": "ICU", "department": "ICU", "status": "available",    "patient_id": None, "equipment": ["ventilator","monitor","oxygen"], "priority_level": 1, "location": "ICU Wing A"},
    {"id": "ICU-102", "type": "ICU", "department": "ICU", "status": "available",    "patient_id": None, "equipment": ["ventilator","monitor","oxygen"], "priority_level": 1, "location": "ICU Wing A"},
    {"id": "ICU-103", "type": "ICU", "department": "ICU", "status": "available",    "patient_id": None, "equipment": ["ventilator","monitor","oxygen"], "priority_level": 1, "location": "ICU Wing A"},
    {"id": "ICU-104", "type": "ICU", "department": "ICU", "status": "available",    "patient_id": None, "equipment": ["ventilator","monitor","oxygen"], "priority_level": 1, "location": "ICU Wing A"},
    {"id": "ICU-105", "type": "ICU", "department": "ICU", "status": "maintenance",  "patient_id": None, "equipment": ["ventilator","monitor"],          "priority_level": 1, "location": "ICU Wing A", "maintenance_until": "14:00"},
    {"id": "ICU-106", "type": "ICU", "department": "ICU", "status": "available",    "patient_id": None, "equipment": ["ventilator","monitor","oxygen"], "priority_level": 1, "location": "ICU Wing B"},
    # ER
    {"id": "ER-201", "type": "ER", "department": "ER", "status": "available",   "patient_id": None, "equipment": ["monitor","oxygen","crash-cart"],   "priority_level": 2, "location": "ER Wing B"},
    {"id": "ER-202", "type": "ER", "department": "ER", "status": "available",   "patient_id": None, "equipment": ["monitor","oxygen"],                "priority_level": 2, "location": "ER Wing B"},
    {"id": "ER-203", "type": "ER", "department": "ER", "status": "available",   "patient_id": None, "equipment": ["monitor","oxygen"],                "priority_level": 2, "location": "ER Wing B"},
    {"id": "ER-204", "type": "ER", "department": "ER", "status": "available",   "patient_id": None, "equipment": ["monitor"],                         "priority_level": 2, "location": "ER Wing B"},
    {"id": "ER-205", "type": "ER", "department": "ER", "status": "available",   "patient_id": None, "equipment": ["monitor","oxygen"],                "priority_level": 2, "location": "ER Wing C"},
    {"id": "ER-206", "type": "ER", "department": "ER", "status": "available",   "patient_id": None, "equipment": ["monitor"],                         "priority_level": 2, "location": "ER Wing C"},
    # Cardiology
    {"id": "CARD-201", "type": "Cardiology", "department": "Cardiology", "status": "available", "patient_id": None, "equipment": ["ECG","monitor","oxygen","defib"], "priority_level": 2, "location": "Cardiology Ward C-2"},
    {"id": "CARD-202", "type": "Cardiology", "department": "Cardiology", "status": "available", "patient_id": None, "equipment": ["ECG","monitor","oxygen"],         "priority_level": 2, "location": "Cardiology Ward C-2"},
    {"id": "CARD-203", "type": "Cardiology", "department": "Cardiology", "status": "available", "patient_id": None, "equipment": ["ECG","monitor"],                  "priority_level": 2, "location": "Cardiology Ward C-2"},
    {"id": "CARD-204", "type": "Cardiology", "department": "Cardiology", "status": "maintenance","patient_id": None, "equipment": ["ECG","monitor"],                 "priority_level": 2, "location": "Cardiology Ward C-2", "maintenance_until": "12:30"},
    # Neurology
    {"id": "NEURO-301", "type": "Neurology", "department": "Neurology", "status": "available", "patient_id": None, "equipment": ["EEG","monitor","oxygen"], "priority_level": 2, "location": "Neurology Ward N-3"},
    {"id": "NEURO-302", "type": "Neurology", "department": "Neurology", "status": "available", "patient_id": None, "equipment": ["monitor","oxygen"],       "priority_level": 2, "location": "Neurology Ward N-3"},
    {"id": "NEURO-303", "type": "Neurology", "department": "Neurology", "status": "available", "patient_id": None, "equipment": ["monitor"],               "priority_level": 2, "location": "Neurology Ward N-3"},
    # General Ward
    {"id": "GW-301", "type": "General", "department": "General", "status": "available", "patient_id": None, "equipment": ["oxygen","call-button"], "priority_level": 3, "location": "General Ward D"},
    {"id": "GW-302", "type": "General", "department": "General", "status": "available", "patient_id": None, "equipment": ["oxygen","call-button"], "priority_level": 3, "location": "General Ward D"},
    {"id": "GW-303", "type": "General", "department": "General", "status": "available", "patient_id": None, "equipment": ["call-button"],          "priority_level": 3, "location": "General Ward D"},
    {"id": "GW-304", "type": "General", "department": "General", "status": "available", "patient_id": None, "equipment": ["call-button"],          "priority_level": 3, "location": "General Ward D"},
    {"id": "GW-305", "type": "General", "department": "General", "status": "available", "patient_id": None, "equipment": ["call-button"],          "priority_level": 3, "location": "General Ward E"},
    {"id": "GW-306", "type": "General", "department": "General", "status": "available", "patient_id": None, "equipment": ["call-button"],          "priority_level": 3, "location": "General Ward E"},
]


# ── patient templates ──────────────────────────────────────────────────────
# Each entry: (patient_id, health_number, status, triage, lat, lon, hours_ago, extras)
# extras: dict with doctor_id, bed_id, treatment_started_h, discharged_h, override_action etc.

DEMO_PATIENTS = [

    # ━━━━━━━━ EN ROUTE — 3 patients (2 ambulance · 1 own transport · ETA 10-15 min) ━━━

    {   # P01 — STEMI [DE] · ambulance · ETA 14 min
        "patient_id": "DEMO-P01-ULM",
        "health_number": "DEMO-DE-001",  # Karl Becker, 68, CAD
        "status": "incoming",
        "has_ambulance": True,
        "triage_level": "IMMEDIATE",
        "chief_complaint": "Crushing chest pain, radiating to left arm, severe sweating",
        "complaint_text": "Sehr starke Brustschmerzen, die in den linken Arm ausstrahlen, starkes Schwitzen",
        "assessment": "Suspected anterior STEMI. BP 88/52, HR 118. Diaphoretic, pale. Cath lab pre-alert required.",
        "red_flags": ["chest_pain_radiation","diaphoresis","hypotension","tachycardia"],
        "suspected_conditions": ["STEMI","Cardiogenic Shock"],
        "risk_score": 10,
        "recommended_action": "Immediate cath lab activation. Aspirin 300mg + Clopidogrel 600mg. IV access ×2. Heparin bolus en route.",
        "time_sensitivity": "Within 5 minutes",
        "language": "de-DE",
        "eta_override": 14,
        "lat": 48.438, "lon": 9.941,
        "qa_transcript": [
            {"question_en": "When did the pain start?",   "question": "Wann hat der Schmerz begonnen?", "answer": "About 20 minutes ago", "original_answer": "Vor etwa 20 Minuten"},
            {"question_en": "Rate pain 1-10?",            "question": "Schmerz auf einer Skala 1-10?",  "answer": "10",                   "original_answer": "10"},
            {"question_en": "Any shortness of breath?",   "question": "Haben Sie Kurzatmigkeit?",      "answer": "Yes, severe",          "original_answer": "Ja, stark"},
            {"question_en": "History of heart disease?",  "question": "Herzerkrankung bekannt?",       "answer": "Yes, stents",          "original_answer": "Ja, Stents"},
        ],
    },

    {   # P02 — Acute severe asthma [UK] · ambulance · ETA 12 min
        "patient_id": "DEMO-P02-ULM",
        "health_number": "DEMO-UK-002",  # Emily Clarke, 35, asthma
        "status": "incoming",
        "has_ambulance": True,
        "triage_level": "EMERGENCY",
        "chief_complaint": "Acute severe asthma — unable to complete sentences, SpO2 88%",
        "complaint_text": "Severe asthma attack, can't breathe properly, blue lips",
        "assessment": "Acute severe asthma. SpO2 88% on air. Silent chest on auscultation. PEFR < 33% predicted.",
        "red_flags": ["low_spo2","respiratory_distress","silent_chest","cyanosis"],
        "suspected_conditions": ["Acute Severe Asthma","Status Asthmaticus"],
        "risk_score": 8,
        "recommended_action": "Back-to-back nebulised salbutamol 5mg + ipratropium. IV hydrocortisone 200mg. O2 to maintain SpO2 >94%. ITU review.",
        "time_sensitivity": "Within 10 minutes",
        "language": "en-GB",
        "eta_override": 12,
        "lat": 48.462, "lon": 9.998,
        "qa_transcript": [
            {"question_en": "How long struggling to breathe?", "question": "How long struggling to breathe?", "answer": "About an hour, getting worse", "original_answer": "About an hour, getting worse"},
            {"question_en": "Using your inhaler?",             "question": "Using your inhaler?",             "answer": "Yes, 10 puffs, not helping",   "original_answer": "Yes, 10 puffs, not helping"},
            {"question_en": "Any previous ITU admissions?",    "question": "Any previous ITU admissions?",    "answer": "Once, 2 years ago",           "original_answer": "Once, 2 years ago"},
        ],
    },

    {   # P03 — Diabetic crisis [TR] · own transport · ETA 11 min
        "patient_id": "DEMO-P03-ULM",
        "health_number": "DEMO-TR-001",  # Ahmet Yılmaz, 59, T2DM + hypertension
        "status": "incoming",
        "has_ambulance": False,
        "triage_level": "URGENT",
        "chief_complaint": "Confusion, extreme thirst, rapid breathing — possible hyperglycaemic crisis",
        "complaint_text": "Çok susadım, kafam karışık, nefes almak zor",
        "assessment": "Probable HHS or DKA. GCS 13. BGL likely >25 mmol/L. Kussmaul breathing noted.",
        "red_flags": ["confusion","hyperglycaemia","rapid_breathing","dehydration"],
        "suspected_conditions": ["Hyperosmolar Hyperglycaemic State","DKA"],
        "risk_score": 8,
        "recommended_action": "IV fluid resuscitation (0.9% NaCl 1L bolus). Insulin infusion protocol. Urine catheter. Hourly glucose.",
        "time_sensitivity": "Within 20 minutes",
        "language": "tr-TR",
        "eta_override": 11,
        "lat": 48.378, "lon": 10.012,
        "qa_transcript": [
            {"question_en": "When did confusion start?",   "question": "Kafa karışıklığı ne zaman başladı?", "answer": "This morning",           "original_answer": "Bu sabah"},
            {"question_en": "Last blood sugar reading?",   "question": "Son kan şekeri değeriniz?",          "answer": "Didn't check, no meter", "original_answer": "Ölçmedim, cihazım yok"},
            {"question_en": "On insulin?",                 "question": "İnsülin kullanıyor musunuz?",        "answer": "No, only metformin",     "original_answer": "Hayır, sadece metformin"},
        ],
    },

    # ━━━━━━━━ IN TREATMENT — 3 patients (all have doctor + bed assigned) ━━━━━━━━━━━━

    {   # P04 — Polytrauma [UK] · ICU · DR001
        "patient_id": "DEMO-P04-ULM",
        "health_number": "DEMO-UK-003",  # Robert Johnson, 79, COPD T2DM
        "status": "in_treatment",
        "triage_level": "IMMEDIATE",
        "chief_complaint": "RTA — head injury, rib fractures, GCS 10",
        "complaint_text": "Road traffic accident, head hit windscreen, difficulty breathing",
        "assessment": "Polytrauma. CT: extradural haematoma R, multiple rib fractures, pulmonary contusion. GCS 10/15. Intubated in ED.",
        "red_flags": ["head_injury","loss_of_consciousness","rib_fractures","low_gcs"],
        "suspected_conditions": ["Extradural Haematoma","Pulmonary Contusion"],
        "risk_score": 10,
        "recommended_action": "Neurosurgery theatre booked. ICU admission. ICP monitoring. Anaesthetics on standby.",
        "time_sensitivity": "Immediate",
        "language": "en-GB",
        "lat": HOSPITAL_LAT, "lon": HOSPITAL_LON,
        "arrival_h": 2.5,
        "treatment_h": 2.3,
        "assigned_doctor_id": "DR001",
        "bed_id": "ICU-101",
        "override_action": "UPGRADE",
        "override_note": "Upgraded to IMMEDIATE post CT findings. Extradural haematoma confirmed.",
        "qa_transcript": [{"question_en": "Conscious after accident?", "question": "Conscious after accident?", "answer": "Briefly, then not", "original_answer": "Briefly, then not"}],
    },

    {   # P05 — GI bleed [DE] · ICU · DR002
        "patient_id": "DEMO-P05-ULM",
        "health_number": "DEMO-DE-003",  # Hans Hoffmann, 67, COPD T2DM
        "status": "in_treatment",
        "triage_level": "EMERGENCY",
        "chief_complaint": "Haematemesis — vomiting blood, large volume, hypotensive",
        "complaint_text": "Blutiges Erbrechen, große Menge, fühle mich sehr schwach",
        "assessment": "Upper GI bleed. Hb 62. BP 78/42 on arrival. Two units pRBC transfusing. OGD booked urgently.",
        "red_flags": ["haematemesis","hypotension","anaemia","tachycardia"],
        "suspected_conditions": ["Peptic Ulcer Bleed","Variceal Bleed"],
        "risk_score": 9,
        "recommended_action": "Urgent OGD. Blood products (pRBC + FFP). PPI infusion. GI surgery standby.",
        "time_sensitivity": "Within 10 minutes",
        "language": "de-DE",
        "lat": HOSPITAL_LAT, "lon": HOSPITAL_LON,
        "arrival_h": 1.8,
        "treatment_h": 1.6,
        "assigned_doctor_id": "DR002",
        "bed_id": "ICU-102",
        "override_action": "APPROVE",
        "override_note": "EMERGENCY confirmed. OGD team mobilised. Blood bank alerted.",
        "qa_transcript": [{"question_en": "Any previous GI bleeding?", "question": "Früher schon Magenblutungen?", "answer": "Yes, 3 years ago", "original_answer": "Ja, vor 3 Jahren"}],
    },

    {   # P06 — Epileptic seizure [TR] · Neurology · DR004
        "patient_id": "DEMO-P06-ULM",
        "health_number": "DEMO-TR-004",  # Zeynep Şahin, 34, epilepsy
        "status": "in_treatment",
        "triage_level": "URGENT",
        "chief_complaint": "Tonic-clonic seizure at workplace, 3 minutes, post-ictal now",
        "complaint_text": "İşyerinde nöbet geçirdim, 3 dakika sürdü, şimdi iyiyim ama kafam karışık",
        "assessment": "Known epilepsy. Breakthrough seizure despite levetiracetam. Post-ictal confusion resolving. No injury.",
        "red_flags": ["seizure","post_ictal","epilepsy_known"],
        "suspected_conditions": ["Breakthrough Seizure","Epilepsy"],
        "risk_score": 6,
        "recommended_action": "IV levetiracetam loading dose. Neurology review. Compliance check. Driving advice.",
        "time_sensitivity": "Within 1 hour",
        "language": "tr-TR",
        "lat": HOSPITAL_LAT, "lon": HOSPITAL_LON,
        "arrival_h": 1.5,
        "treatment_h": 1.3,
        "assigned_doctor_id": "DR004",
        "bed_id": "NEURO-301",
        "override_action": "APPROVE",
        "override_note": "Neurology review complete. Dose adjustment planned. Safe to discharge later today.",
        "qa_transcript": [{"question_en": "When was your last seizure?", "question": "Son nöbetiniz ne zaman oldu?", "answer": "18 months ago", "original_answer": "18 ay önce"}],
    },

    # ━━━━━━━━ DISCHARGED — 1 patient ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    {   # P07 — Scalp laceration [UK] · discharged
        "patient_id": "DEMO-P07-ULM",
        "health_number": "DEMO-UK-009",  # Henry Moore, 85
        "status": "discharged",
        "triage_level": "STANDARD",
        "chief_complaint": "Slip and fall at home — laceration scalp, no LOC, bruising",
        "complaint_text": "Slipped on wet floor, cut my head, no blackout",
        "assessment": "Scalp laceration 3cm, sutured. Head CT negative. No anticoagulants. Safe to discharge.",
        "red_flags": ["head_injury","elderly"],
        "suspected_conditions": ["Scalp Laceration","Minor Head Injury"],
        "risk_score": 3,
        "recommended_action": "Discharged with head injury advice sheet. Sutures out in 7 days at GP.",
        "time_sensitivity": "Within 1 hour",
        "language": "en-GB",
        "lat": HOSPITAL_LAT, "lon": HOSPITAL_LON,
        "arrival_h": 4.5,
        "treatment_h": 4.2,
        "discharged_h": 2.0,
        "qa_transcript": [{"question_en": "Did you lose consciousness?", "question": "Did you lose consciousness?", "answer": "No, was alert throughout", "original_answer": "No, was alert throughout"}],
    },
]


# ── localStorage state builder ─────────────────────────────────────────────

def _build_local_storage(patients: list[dict]) -> dict:
    """Return the localStorage JSON the dashboard should inject on load."""
    now_iso   = datetime.now(timezone.utc).isoformat()
    doctor_map = {d["id"]: d["name"] for d in DOCTORS}

    doctor_assignments = []
    bed_assignments    = []
    patient_actions: dict = {}

    for p in patients:
        pid = p["patient_id"]
        actions: list = []

        # entry
        arrived_iso = _ago(p.get("arrival_h", 0.5))
        actions.append({"id": 1, "type": "patient_entry", "timestamp": _ago(p.get("arrival_h", 0.5) + 0.05),
                        "message": "Patient registered via AI triage system"})

        if p.get("status") in ("in_treatment", "discharged"):
            actions.append({"id": 2, "type": "patient_arrived", "timestamp": arrived_iso, "message": "Patient arrived at Universitätsklinikum Ulm"})

        if p.get("assigned_doctor_id"):
            assign_iso = _ago(p.get("treatment_h", 0) + 0.1)
            doctor_name = doctor_map.get(p["assigned_doctor_id"], p["assigned_doctor_id"])
            doctor_assignments.append({
                "patient_id":         pid,
                "assigned_doctor":    doctor_name,
                "assigned_doctor_id": p["assigned_doctor_id"],
                "doctor_assigned_at": assign_iso,
            })
            actions.append({"id": 3, "type": "doctor_assigned", "timestamp": assign_iso,
                            "message": f"Assigned to {doctor_name}",
                            "assigned_doctor": doctor_name, "assigned_doctor_id": p["assigned_doctor_id"]})

        if p.get("bed_id"):
            bed_iso = _ago(p.get("treatment_h", 0))
            bed_assignments.append({
                "patientId":      pid,
                "bedId":          p["bed_id"],
                "bed_assigned_at":  bed_iso,
                "status":         p.get("status", "in_treatment"),
            })
            actions.append({"id": 4, "type": "bed_assigned", "timestamp": bed_iso,
                            "message": f"Bed {p['bed_id']} assigned", "bedId": p["bed_id"]})

        if p.get("override_action"):
            override_iso = _ago(p.get("treatment_h", 0) + 0.05)
            actions.append({"id": 5, "type": "triage_changed", "timestamp": override_iso,
                            "message": f"Physician {p['override_action'].lower()} triage",
                            "from": "AI", "to": p["triage_level"]})

        if p.get("status") == "discharged":
            actions.append({"id": 6, "type": "discharged", "timestamp": _ago(p.get("discharged_h", 0.5)),
                            "message": "Patient discharged"})

        patient_actions[pid] = actions

    amb_pids = [p["patient_id"] for p in patients if p.get("has_ambulance")]
    amb_speeds = {p["patient_id"]: (88 if p.get("triage_level") in ("IMMEDIATE","EMERGENCY") else 80)
                  for p in patients if p.get("has_ambulance")}

    return {
        "doctorAssignments": json.dumps(doctor_assignments),
        "bedAssignments":    json.dumps(bed_assignments),
        "patientActions":    json.dumps(patient_actions),
        "ambulancePatients": json.dumps(amb_pids),
        "ambulanceSpeeds":   json.dumps(amb_speeds),
    }


# ── main seed function ─────────────────────────────────────────────────────

def run_demo_seed() -> dict:
    """Clear queue and insert all demo patients. Returns localStorage state."""

    if not DB_PATH.exists():
        return {"ok": False, "error": f"Queue DB not found at {DB_PATH}. Start the server first."}

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    # ── clear ──
    conn.execute("DELETE FROM patient_queue")
    conn.commit()

    seeded = 0
    for p in DEMO_PATIENTS:
        now_str  = datetime.now(timezone.utc).isoformat()
        arr_h    = p.get("arrival_h", 0)
        treat_h  = p.get("treatment_h", 0)
        dis_h    = p.get("discharged_h")
        status   = p["status"]

        arrival_time         = _ago(arr_h) if status in ("in_treatment","discharged") else None
        treatment_started_at = _ago(treat_h) if status in ("in_treatment","discharged") else None
        discharged_at        = _ago(dis_h) if dis_h else None
        timestamp            = _ago(arr_h + 0.1)

        # eta for en-route only
        if status == "incoming":
            eta = p.get("eta_override") or _eta(p.get("lat", HOSPITAL_LAT), p.get("lon", HOSPITAL_LON))
        else:
            eta = None

        # Build override_note with timestamp prefix (matches real format)
        override_note = None
        if p.get("override_action") and p.get("override_note"):
            ts_str  = (datetime.now(timezone.utc) - timedelta(hours=treat_h)).strftime("%Y-%m-%d %H:%M UTC")
            override_note = f"[{ts_str}] [{p['override_action']}→{p['triage_level']}] {p['override_note']}"

        # Ambulance dispatch data for ambulance demo patients
        db_override_action = p.get("override_action")
        amb_dispatch_at = None
        amb_eta_patient = None
        if p.get("has_ambulance") and status == "incoming":
            # Demo ambulances are already dispatched; set dispatch time ~eta minutes ago
            amb_eta_patient = eta or 10
            # Dispatch timestamp: half the ETA in the past (ambulance midway)
            dispatch_minutes_ago = max(1, int(amb_eta_patient * 0.5))
            amb_dispatch_at = (datetime.now(timezone.utc) - timedelta(minutes=dispatch_minutes_ago)).isoformat()
            db_override_action = "AMBULANCE"  # already dispatched in demo

        conn.execute("""
            INSERT OR REPLACE INTO patient_queue
            (patient_id, timestamp, created_at, triage_level, chief_complaint,
             red_flags, assessment, suspected_conditions, risk_score,
             recommended_action, time_sensitivity, source_guidelines,
             eta_minutes, arrival_time, location_lat, location_lon,
             language, destination_hospital, status, updated_at,
             qa_transcript, health_number, has_photo, photo_count, complaint_text,
             ai_triage_level, treatment_started_at, discharged_at,
             override_action, override_note, amb_dispatch_at, amb_eta_patient)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            p["patient_id"],
            timestamp,
            timestamp,   # created_at = same as timestamp (submission time, not seed time)
            p["triage_level"],
            p["chief_complaint"],
            json.dumps(p.get("red_flags", [])),
            p.get("assessment",""),
            json.dumps(p.get("suspected_conditions", [])),
            p.get("risk_score", 5),
            p.get("recommended_action",""),
            p.get("time_sensitivity",""),
            "[]",
            eta,
            arrival_time,
            p.get("lat", HOSPITAL_LAT),
            p.get("lon", HOSPITAL_LON),
            p.get("language","de-DE"),
            HOSPITAL,
            status,
            now_str,
            json.dumps(p.get("qa_transcript",[])),
            p.get("health_number",""),
            0,
            0,
            p.get("complaint_text",""),
            p["triage_level"],
            treatment_started_at,
            discharged_at,
            db_override_action,
            override_note,
            amb_dispatch_at,
            amb_eta_patient,
        ))
        seeded += 1

    conn.commit()
    conn.close()

    local_storage = _build_local_storage(DEMO_PATIENTS)

    return {
        "ok":           True,
        "seeded":       seeded,
        "hospital":     HOSPITAL,
        "beds":         BEDS,
        "doctors":      DOCTORS,
        "localStorage": local_storage,
    }


# ── standalone ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    result = run_demo_seed()
    print(json.dumps({k: v for k, v in result.items() if k != "beds" and k != "doctors"}, indent=2, ensure_ascii=False))
    print(f"\n✅  Seeded {result['seeded']} patients for {result['hospital']}")
