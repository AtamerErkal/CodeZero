"""
Health Record Database — CodeZero
===================================
Simulates a national health ID system (eNabiz / NHS / eDevlet style).
Each patient has a unique health number. Doctors enter it to pull full history.

Schema:
  patients        — demographics, photo, health_number
  diagnoses       — ICD-10 coded diagnoses
  medications     — current and past prescriptions
  lab_results     — blood tests, imaging reports
  vitals          — BP, HR, SpO2, weight, height, BMI
  visits          — past ER / outpatient visits
  allergies       — drug and food allergies
  emergency_contacts

All data is simulated for demo purposes.
"""
from __future__ import annotations
import json
import logging
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "data" / "health_records.db"


def _conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


def init_db() -> None:
    """Create all tables and seed demo patients."""
    with _conn() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS patients (
            health_number  TEXT PRIMARY KEY,
            first_name     TEXT NOT NULL,
            last_name      TEXT NOT NULL,
            date_of_birth  TEXT NOT NULL,
            sex            TEXT NOT NULL,
            blood_type     TEXT,
            nationality    TEXT DEFAULT 'DE',
            email          TEXT,
            phone          TEXT,
            address        TEXT,
            emergency_name TEXT,
            emergency_phone TEXT,
            photo_url      TEXT,
            insurance_id   TEXT,
            gp_name        TEXT,
            notes          TEXT
        );

        CREATE TABLE IF NOT EXISTS diagnoses (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            health_number TEXT NOT NULL,
            icd_code    TEXT,
            description TEXT NOT NULL,
            status      TEXT DEFAULT 'active',
            diagnosed_date TEXT,
            diagnosing_doctor TEXT,
            notes       TEXT,
            FOREIGN KEY (health_number) REFERENCES patients(health_number)
        );

        CREATE TABLE IF NOT EXISTS medications (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            health_number TEXT NOT NULL,
            name        TEXT NOT NULL,
            dosage      TEXT,
            frequency   TEXT,
            start_date  TEXT,
            end_date    TEXT,
            prescribing_doctor TEXT,
            status      TEXT DEFAULT 'active',
            FOREIGN KEY (health_number) REFERENCES patients(health_number)
        );

        CREATE TABLE IF NOT EXISTS lab_results (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            health_number TEXT NOT NULL,
            test_name   TEXT NOT NULL,
            value       TEXT,
            unit        TEXT,
            reference_range TEXT,
            status      TEXT DEFAULT 'normal',
            test_date   TEXT,
            lab_name    TEXT,
            FOREIGN KEY (health_number) REFERENCES patients(health_number)
        );

        CREATE TABLE IF NOT EXISTS vitals (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            health_number TEXT NOT NULL,
            recorded_at TEXT NOT NULL,
            bp_systolic INTEGER,
            bp_diastolic INTEGER,
            heart_rate  INTEGER,
            spo2        REAL,
            temperature REAL,
            weight_kg   REAL,
            height_cm   REAL,
            bmi         REAL,
            glucose     REAL,
            FOREIGN KEY (health_number) REFERENCES patients(health_number)
        );

        CREATE TABLE IF NOT EXISTS visits (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            health_number TEXT NOT NULL,
            visit_date  TEXT NOT NULL,
            visit_type  TEXT,
            hospital    TEXT,
            department  TEXT,
            chief_complaint TEXT,
            diagnosis   TEXT,
            treatment   TEXT,
            discharge_notes TEXT,
            attending_doctor TEXT,
            FOREIGN KEY (health_number) REFERENCES patients(health_number)
        );

        CREATE TABLE IF NOT EXISTS allergies (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            health_number TEXT NOT NULL,
            allergen    TEXT NOT NULL,
            reaction    TEXT,
            severity    TEXT DEFAULT 'moderate',
            confirmed_date TEXT,
            FOREIGN KEY (health_number) REFERENCES patients(health_number)
        );
        """)
        _seed_demo_patients(con)
    logger.info("Health DB initialized at %s", DB_PATH)


def _seed_demo_patients(con: sqlite3.Connection) -> None:
    """Insert demo patients if not already present."""
    existing = con.execute("SELECT COUNT(*) FROM patients").fetchone()[0]
    if existing > 0:
        return

    patients = [
        # German patient
        ("DE-1985-447291", "Klaus", "Müller", "1985-03-14", "Male", "A+",
         "DE", "k.mueller@email.de", "+49 711 123 4567",
         "Kriegsbergstraße 10, 70174 Stuttgart",
         "Greta Müller", "+49 711 987 6543", None,
         "AOK-BW 123456789", "Dr. Hans Becker",
         "Patient has known cardiac history. Takes statins daily."),

        # Turkish patient
        ("TR-1972-881043", "Ahmet", "Yılmaz", "1972-07-22", "Male", "B+",
         "TR", "a.yilmaz@email.com", "+90 532 111 2233",
         "Atatürk Cad. No: 15, 34000 İstanbul",
         "Fatma Yılmaz", "+90 532 444 5566", None,
         "SGK-5512873690", "Dr. Mehmet Kaya",
         "Type 2 diabetes controlled with metformin. Hypertension."),

        # UK patient
        ("UK-1990-334872", "Emily", "Clarke", "1990-11-05", "Female", "O-",
         "UK", "e.clarke@email.co.uk", "+44 7700 900 123",
         "14 Baker Street, London W1U 3BW",
         "James Clarke", "+44 7700 900 456", None,
         "NHS-789012345", "Dr. Sarah Thompson",
         "Asthma since childhood. Carries Ventolin inhaler."),

        # Demo emergency patient
        ("DE-1978-992817", "Maria", "Schmidt", "1978-09-30", "Female", "AB+",
         "DE", "m.schmidt@email.de", "+49 89 555 1234",
         "Marienplatz 5, 80331 München",
         "Peter Schmidt", "+49 89 555 5678", None,
         "TK-987654321", "Dr. Elisabeth Weber",
         "No significant past medical history. Occasional migraines."),
    ]

    con.executemany("""
        INSERT OR IGNORE INTO patients VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, patients)

    # Diagnoses
    diagnoses = [
        ("DE-1985-447291", "I25.10", "Coronary artery disease without angina pectoris", "active", "2019-06-10", "Dr. Becker", "Managed with medication"),
        ("DE-1985-447291", "E78.5",  "Hyperlipidaemia", "active", "2018-03-05", "Dr. Becker", "Statin therapy"),
        ("DE-1985-447291", "I10",    "Essential hypertension", "active", "2017-01-20", "Dr. Becker", "ACE inhibitor"),

        ("TR-1972-881043", "E11.9",  "Type 2 diabetes mellitus without complications", "active", "2015-04-12", "Dr. Kaya", "Metformin 1000mg BD"),
        ("TR-1972-881043", "I10",    "Essential hypertension", "active", "2016-08-03", "Dr. Kaya", "Amlodipine 5mg"),
        ("TR-1972-881043", "E11.51", "Diabetic peripheral angiopathy", "active", "2022-11-19", "Dr. Özdemir", "Annual review"),

        ("UK-1990-334872", "J45.20", "Mild intermittent asthma, uncomplicated", "active", "2005-03-22", "Dr. Thompson", "SABA as needed"),
        ("UK-1990-334872", "J30.1",  "Allergic rhinitis due to pollen", "active", "2012-07-14", "Dr. Thompson", "Seasonal antihistamines"),

        ("DE-1978-992817", "G43.909","Migraine, unspecified, not intractable", "active", "2020-02-28", "Dr. Weber", "Triptans PRN"),
    ]

    con.executemany("""
        INSERT INTO diagnoses (health_number,icd_code,description,status,diagnosed_date,diagnosing_doctor,notes)
        VALUES (?,?,?,?,?,?,?)
    """, diagnoses)

    # Medications
    medications = [
        ("DE-1985-447291", "Atorvastatin 40mg", "40mg", "Once daily (evening)", "2019-06-15", None, "Dr. Becker", "active"),
        ("DE-1985-447291", "Ramipril 5mg",       "5mg",  "Once daily (morning)", "2017-01-25", None, "Dr. Becker", "active"),
        ("DE-1985-447291", "Aspirin 100mg",       "100mg","Once daily",           "2019-06-15", None, "Dr. Becker", "active"),
        ("DE-1985-447291", "Bisoprolol 5mg",      "5mg",  "Once daily",           "2020-03-10", None, "Dr. Becker", "active"),

        ("TR-1972-881043", "Metformin 1000mg", "1000mg", "Twice daily with meals", "2015-04-15", None, "Dr. Kaya", "active"),
        ("TR-1972-881043", "Amlodipine 5mg",   "5mg",    "Once daily",             "2016-08-10", None, "Dr. Kaya", "active"),
        ("TR-1972-881043", "Aspirin 100mg",    "100mg",  "Once daily",             "2018-06-01", None, "Dr. Kaya", "active"),

        ("UK-1990-334872", "Salbutamol inhaler 100mcg", "2 puffs", "PRN (as needed)", "2005-03-25", None, "Dr. Thompson", "active"),
        ("UK-1990-334872", "Loratadine 10mg",           "10mg",    "Once daily (seasonal)", "2012-07-20", "2012-10-01", "Dr. Thompson", "inactive"),

        ("DE-1978-992817", "Sumatriptan 50mg", "50mg", "PRN max 2/day", "2020-03-01", None, "Dr. Weber", "active"),
    ]

    con.executemany("""
        INSERT INTO medications (health_number,name,dosage,frequency,start_date,end_date,prescribing_doctor,status)
        VALUES (?,?,?,?,?,?,?,?)
    """, medications)

    # Vitals — most recent first
    vitals = [
        ("DE-1985-447291", "2026-01-15T09:30:00", 138, 88, 74, 98.0, 36.7, 84.5, 178.0, 26.7, 5.1),
        ("DE-1985-447291", "2025-10-22T10:00:00", 142, 91, 78, 97.5, 36.5, 85.0, 178.0, 26.8, 5.4),
        ("DE-1985-447291", "2025-07-08T08:45:00", 136, 86, 71, 98.2, 36.6, 84.0, 178.0, 26.5, 5.0),

        ("TR-1972-881043", "2026-02-01T11:00:00", 148, 94, 82, 97.0, 37.0, 91.0, 172.0, 30.8, 8.2),
        ("TR-1972-881043", "2025-11-15T09:15:00", 152, 96, 85, 96.5, 36.9, 92.5, 172.0, 31.3, 9.1),

        ("UK-1990-334872", "2026-01-20T14:30:00", 118, 76, 68, 99.0, 36.4, 62.0, 168.0, 21.9, 4.8),
        ("UK-1990-334872", "2025-09-10T16:00:00", 115, 74, 66, 98.8, 36.3, 61.5, 168.0, 21.8, 4.7),

        ("DE-1978-992817", "2026-02-10T10:00:00", 122, 78, 70, 99.0, 36.5, 68.0, 165.0, 25.0, 4.9),
    ]

    con.executemany("""
        INSERT INTO vitals (health_number,recorded_at,bp_systolic,bp_diastolic,heart_rate,spo2,temperature,weight_kg,height_cm,bmi,glucose)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, vitals)

    # Lab results
    labs = [
        ("DE-1985-447291", "HbA1c",         "5.4%",     "%",      "< 5.7%",       "normal",  "2026-01-15", "Labor Stuttgart"),
        ("DE-1985-447291", "LDL Cholesterol","2.1 mmol/L","mmol/L","< 1.8 mmol/L", "high",    "2026-01-15", "Labor Stuttgart"),
        ("DE-1985-447291", "Troponin I",     "0.01 ng/mL","ng/mL","< 0.04 ng/mL", "normal",  "2025-10-22", "Labor Stuttgart"),
        ("DE-1985-447291", "eGFR",           "78 ml/min","ml/min","≥ 60 ml/min",  "normal",  "2026-01-15", "Labor Stuttgart"),
        ("DE-1985-447291", "CRP",            "4.2 mg/L", "mg/L",  "< 5.0 mg/L",   "normal",  "2026-01-15", "Labor Stuttgart"),

        ("TR-1972-881043", "HbA1c",         "8.2%",     "%",      "< 7.0%",       "high",    "2026-02-01", "Acıbadem Lab"),
        ("TR-1972-881043", "Fasting Glucose","9.1 mmol/L","mmol/L","3.9-5.5",     "high",    "2026-02-01", "Acıbadem Lab"),
        ("TR-1972-881043", "Creatinine",     "1.3 mg/dL","mg/dL", "0.7-1.2 mg/dL","high",   "2026-02-01", "Acıbadem Lab"),

        ("UK-1990-334872", "Peak Flow",      "480 L/min","L/min", "400-550 L/min","normal",  "2026-01-20", "NHS Lab London"),
        ("UK-1990-334872", "IgE (total)",    "180 IU/mL","IU/mL", "< 100 IU/mL", "high",    "2026-01-20", "NHS Lab London"),

        ("DE-1978-992817", "Full Blood Count","Normal",  "",       "",             "normal",  "2026-02-10", "Labor München"),
        ("DE-1978-992817", "Thyroid (TSH)",  "2.1 mIU/L","mIU/L","0.4-4.0 mIU/L","normal", "2026-02-10", "Labor München"),
    ]

    con.executemany("""
        INSERT INTO lab_results (health_number,test_name,value,unit,reference_range,status,test_date,lab_name)
        VALUES (?,?,?,?,?,?,?,?)
    """, labs)

    # Allergies
    allergies = [
        ("DE-1985-447291", "Penicillin",  "Anaphylaxis", "severe",   "2010-05-12"),
        ("DE-1985-447291", "Ibuprofen",   "GI bleed",    "moderate", "2015-08-20"),
        ("TR-1972-881043", "Sulfonamides","Rash",         "mild",     "2018-03-01"),
        ("UK-1990-334872", "Latex",       "Urticaria",    "moderate", "2008-11-30"),
        ("UK-1990-334872", "Aspirin",     "Bronchospasm", "severe",   "2015-02-14"),
    ]

    con.executemany("""
        INSERT INTO allergies (health_number,allergen,reaction,severity,confirmed_date)
        VALUES (?,?,?,?,?)
    """, allergies)

    # Past visits
    visits = [
        ("DE-1985-447291", "2025-11-03", "Emergency", "Klinikum Stuttgart – Katharinenhospital", "Cardiology",
         "Chest tightness and palpitations", "Stable CAD — no acute event", "IV nitrates, monitoring", "Discharged after 6h observation", "Dr. Schreiber"),
        ("DE-1985-447291", "2024-06-18", "Outpatient", "Klinikum Stuttgart – Katharinenhospital", "Cardiology",
         "Routine cardiology follow-up", "Stable CAD", "Medication adjustment", "Continue current medications", "Dr. Schreiber"),
        ("DE-1985-447291", "2023-01-09", "Emergency", "Robert-Bosch-Krankenhaus Stuttgart", "Emergency",
         "Hypertensive crisis BP 185/110", "Hypertensive urgency", "IV labetalol, oral agents restarted", "BP controlled, discharged", "Dr. Hoffmann"),

        ("TR-1972-881043", "2025-12-01", "Emergency", "Acıbadem Hastanesi", "Emergency",
         "Hyperglycemia, blood sugar 22 mmol/L", "DKA — mild", "IV insulin, fluids", "Admitted 2 days, discharged", "Dr. Özdemir"),
        ("TR-1972-881043", "2024-09-15", "Outpatient", "İstanbul Üniversitesi", "Endocrinology",
         "Diabetes review", "T2DM — suboptimal control", "Insulin addition discussed", "Metformin dose increased", "Dr. Kaya"),

        ("UK-1990-334872", "2025-08-22", "Emergency", "King's College Hospital London", "Emergency",
         "Acute asthma attack", "Moderate acute asthma", "Nebulised salbutamol x3, steroids", "Discharged with short oral steroid course", "Dr. Patel"),
        ("UK-1990-334872", "2024-04-10", "Outpatient", "Guy's Hospital London", "Respiratory",
         "Annual asthma review", "Well-controlled asthma", "Spirometry normal", "Continue SABA, annual review", "Dr. Thompson"),

        ("DE-1978-992817", "2026-01-20", "Emergency", "LMU Klinikum München – Großhadern", "Neurology",
         "Severe migraine with visual aura", "Migraine with aura", "IV paracetamol + sumatriptan", "Discharged after 4h", "Dr. Braun"),
    ]

    con.executemany("""
        INSERT INTO visits (health_number,visit_date,visit_type,hospital,department,chief_complaint,diagnosis,treatment,discharge_notes,attending_doctor)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """, visits)

    logger.info("Seeded %d demo patients with full health history", len(patients))


def get_patient(health_number: str) -> Optional[dict]:
    """Fetch patient demographics. Returns None if not found."""
    with _conn() as con:
        row = con.execute("SELECT * FROM patients WHERE health_number=?", (health_number,)).fetchone()
        if not row:
            return None
        return dict(row)


def get_full_record(health_number: str) -> Optional[dict]:
    """Fetch complete health record for a patient."""
    patient = get_patient(health_number)
    if not patient:
        return None
    with _conn() as con:
        return {
            "patient":     patient,
            "diagnoses":   [dict(r) for r in con.execute("SELECT * FROM diagnoses WHERE health_number=? ORDER BY diagnosed_date DESC", (health_number,)).fetchall()],
            "medications": [dict(r) for r in con.execute("SELECT * FROM medications WHERE health_number=? ORDER BY status,start_date DESC", (health_number,)).fetchall()],
            "lab_results": [dict(r) for r in con.execute("SELECT * FROM lab_results WHERE health_number=? ORDER BY test_date DESC", (health_number,)).fetchall()],
            "vitals":      [dict(r) for r in con.execute("SELECT * FROM vitals WHERE health_number=? ORDER BY recorded_at DESC LIMIT 10", (health_number,)).fetchall()],
            "visits":      [dict(r) for r in con.execute("SELECT * FROM visits WHERE health_number=? ORDER BY visit_date DESC LIMIT 10", (health_number,)).fetchall()],
            "allergies":   [dict(r) for r in con.execute("SELECT * FROM allergies WHERE health_number=?", (health_number,)).fetchall()],
        }


def list_demo_health_numbers() -> list[str]:
    """Return all health numbers in the DB (for demo picker)."""
    with _conn() as con:
        return [r[0] for r in con.execute("SELECT health_number FROM patients ORDER BY nationality").fetchall()]


# Initialize on import
init_db()