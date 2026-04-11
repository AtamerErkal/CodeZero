"""
Health Record Database — CodeZero v3
======================================
30 rich demo patients: 10 DE + 10 TR + 10 UK
Health number format: DEMO-DE-001, DEMO-TR-001, DEMO-UK-001

v3 additions:
  - Extended anamnesis (symptoms, mood, social/family history)
  - Surgical reports + anaesthesia protocols
  - Imaging results (US, RX, MRI, CT, ECG, EMG, etc.)
  - Doctor notes and assessments (SOAP format)
  - Appointment schedules
  - Patient declarations and treatment consents
  - Inter-specialty consultation letters
  - Medication side effects and adherence notes
"""
from __future__ import annotations
import logging, sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)
DB_PATH = Path(__file__).parent.parent / "data" / "health_records.db"


def _conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con


def _migrate(con):
    """Migrate legacy DB schema to current version."""
    existing_patients = {r[1] for r in con.execute("PRAGMA table_info(patients)").fetchall()}
    patient_migrations = [
        ("language",          "TEXT DEFAULT 'de-DE'"),
        ("height_cm",         "REAL"),
        ("weight_kg",         "REAL"),
        ("smoking_status",    "TEXT"),
        ("alcohol_use",       "TEXT"),
        ("occupation",        "TEXT"),
        ("marital_status",    "TEXT"),
        ("family_history",    "TEXT"),
        ("social_history",    "TEXT"),
        ("mood_assessment",   "TEXT"),
        ("functional_status", "TEXT"),
    ]
    for col, defn in patient_migrations:
        if col not in existing_patients:
            con.execute(f"ALTER TABLE patients ADD COLUMN {col} {defn}")
            logger.info("Migrated patients table: added column %s", col)

    # Migrate medications table
    try:
        existing_meds = {r[1] for r in con.execute("PRAGMA table_info(medications)").fetchall()}
        if existing_meds:
            med_migrations = [
                ("side_effects",    "TEXT"),
                ("adherence_notes", "TEXT")
            ]
            for col, defn in med_migrations:
                if col not in existing_meds:
                    con.execute(f"ALTER TABLE medications ADD COLUMN {col} {defn}")
                    logger.info("Migrated medications table: added column %s", col)
    except Exception as e:
        logger.warning(f"Could not migrate medications table: {e}")

    con.commit()


def _do_init_db():
    with _conn() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS patients (
            health_number     TEXT PRIMARY KEY,
            first_name        TEXT NOT NULL,
            last_name         TEXT NOT NULL,
            date_of_birth     TEXT NOT NULL,
            sex               TEXT NOT NULL,
            blood_type        TEXT,
            nationality       TEXT DEFAULT 'DE',
            language          TEXT DEFAULT 'de-DE',
            email             TEXT,
            phone             TEXT,
            address           TEXT,
            emergency_name    TEXT,
            emergency_phone   TEXT,
            insurance_id      TEXT,
            gp_name           TEXT,
            height_cm         REAL,
            weight_kg         REAL,
            notes             TEXT,
            smoking_status    TEXT,
            alcohol_use       TEXT,
            occupation        TEXT,
            marital_status    TEXT,
            family_history    TEXT,
            social_history    TEXT,
            mood_assessment   TEXT,
            functional_status TEXT
        );

        CREATE TABLE IF NOT EXISTS diagnoses (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            health_number     TEXT NOT NULL,
            icd_code          TEXT,
            description       TEXT NOT NULL,
            status            TEXT DEFAULT 'active',
            diagnosed_date    TEXT,
            diagnosing_doctor TEXT,
            notes             TEXT
        );

        CREATE TABLE IF NOT EXISTS medications (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            health_number      TEXT NOT NULL,
            name               TEXT NOT NULL,
            dosage             TEXT,
            frequency          TEXT,
            start_date         TEXT,
            end_date           TEXT,
            prescribing_doctor TEXT,
            status             TEXT DEFAULT 'active',
            side_effects       TEXT,
            adherence_notes    TEXT
        );

        CREATE TABLE IF NOT EXISTS lab_results (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            health_number   TEXT NOT NULL,
            test_name       TEXT NOT NULL,
            value           TEXT,
            unit            TEXT,
            reference_range TEXT,
            status          TEXT DEFAULT 'normal',
            test_date       TEXT,
            lab_name        TEXT,
            ordering_doctor TEXT,
            clinical_note   TEXT
        );

        CREATE TABLE IF NOT EXISTS vitals (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            health_number    TEXT NOT NULL,
            recorded_at      TEXT NOT NULL,
            bp_systolic      INTEGER,
            bp_diastolic     INTEGER,
            heart_rate       INTEGER,
            spo2             REAL,
            temperature      REAL,
            weight_kg        REAL,
            height_cm        REAL,
            bmi              REAL,
            glucose          REAL,
            respiratory_rate INTEGER,
            pain_scale       INTEGER
        );

        CREATE TABLE IF NOT EXISTS visits (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            health_number    TEXT NOT NULL,
            visit_date       TEXT NOT NULL,
            visit_type       TEXT,
            hospital         TEXT,
            department       TEXT,
            chief_complaint  TEXT,
            diagnosis        TEXT,
            treatment        TEXT,
            discharge_notes  TEXT,
            attending_doctor TEXT,
            duration_days    INTEGER,
            follow_up_date   TEXT
        );

        CREATE TABLE IF NOT EXISTS allergies (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            health_number  TEXT NOT NULL,
            allergen       TEXT NOT NULL,
            reaction       TEXT,
            severity       TEXT DEFAULT 'moderate',
            confirmed_date TEXT,
            notes          TEXT
        );

        CREATE TABLE IF NOT EXISTS surgeries (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            health_number     TEXT NOT NULL,
            surgery_date      TEXT NOT NULL,
            procedure_name    TEXT NOT NULL,
            indication        TEXT,
            surgeon           TEXT,
            assistant_surgeon TEXT,
            hospital          TEXT,
            duration_minutes  INTEGER,
            approach          TEXT,
            findings          TEXT,
            complications     TEXT,
            outcome           TEXT,
            postop_notes      TEXT
        );

        CREATE TABLE IF NOT EXISTS anesthesia_records (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            health_number    TEXT NOT NULL,
            surgery_id       INTEGER,
            anesthesia_date  TEXT NOT NULL,
            anesthesiologist TEXT,
            anesthesia_type  TEXT,
            preop_assessment TEXT,
            asa_class        TEXT,
            agents_used      TEXT,
            airway_management TEXT,
            intraop_events   TEXT,
            recovery_notes   TEXT
        );

        CREATE TABLE IF NOT EXISTS imaging (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            health_number   TEXT NOT NULL,
            study_date      TEXT NOT NULL,
            modality        TEXT NOT NULL,
            body_region     TEXT,
            indication      TEXT,
            findings        TEXT,
            impression      TEXT,
            radiologist     TEXT,
            ordering_doctor TEXT,
            facility        TEXT
        );

        CREATE TABLE IF NOT EXISTS ecg_records (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            health_number   TEXT NOT NULL,
            recorded_at     TEXT NOT NULL,
            rhythm          TEXT,
            rate_bpm        INTEGER,
            pr_interval_ms  INTEGER,
            qrs_duration_ms INTEGER,
            qt_qtc_ms       TEXT,
            axis            TEXT,
            findings        TEXT,
            interpretation  TEXT,
            ordering_doctor TEXT
        );

        CREATE TABLE IF NOT EXISTS emg_records (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            health_number  TEXT NOT NULL,
            study_date     TEXT NOT NULL,
            muscles_tested TEXT,
            nerves_tested  TEXT,
            findings       TEXT,
            impression     TEXT,
            neurologist    TEXT,
            facility       TEXT
        );

        CREATE TABLE IF NOT EXISTS doctor_notes (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            health_number TEXT NOT NULL,
            note_date     TEXT NOT NULL,
            note_type     TEXT,
            author        TEXT,
            department    TEXT,
            subjective    TEXT,
            objective     TEXT,
            assessment    TEXT,
            plan          TEXT,
            full_note     TEXT
        );

        CREATE TABLE IF NOT EXISTS appointments (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            health_number    TEXT NOT NULL,
            appointment_date TEXT NOT NULL,
            appointment_time TEXT,
            department       TEXT,
            doctor           TEXT,
            hospital         TEXT,
            purpose          TEXT,
            status           TEXT DEFAULT 'scheduled',
            notes            TEXT
        );

        CREATE TABLE IF NOT EXISTS consents (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            health_number  TEXT NOT NULL,
            consent_date   TEXT NOT NULL,
            consent_type   TEXT NOT NULL,
            procedure      TEXT,
            obtained_by    TEXT,
            patient_signed INTEGER DEFAULT 1,
            witness        TEXT,
            notes          TEXT
        );

        CREATE TABLE IF NOT EXISTS consultations (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            health_number     TEXT NOT NULL,
            consult_date      TEXT NOT NULL,
            requesting_doctor TEXT,
            consulting_doctor TEXT,
            specialty         TEXT,
            reason            TEXT,
            findings          TEXT,
            recommendations   TEXT,
            urgency           TEXT DEFAULT 'routine'
        );
        """)
        _migrate(con)
        _seed(con)

def init_db():
    try:
        _do_init_db()
    except sqlite3.OperationalError as e:
        logger.warning("Database schema error during init: %s. Recreating database.", e)
        # If the DB schema is profoundly broken from a previous version, wipe it and start fresh.
        try:
            if DB_PATH.exists():
                DB_PATH.unlink()
            _do_init_db()
        except Exception as retry_e:
            logger.error("Failed to recreate database: %s", retry_e)

def _seed(con):
    demo_count = con.execute(
        "SELECT COUNT(*) FROM patients WHERE health_number LIKE 'DEMO-%'"
    ).fetchone()[0]

    if demo_count >= 30:
        checks = [
            con.execute("SELECT COUNT(*) FROM vitals     WHERE health_number LIKE 'DEMO-%'").fetchone()[0] > 0,
            con.execute("SELECT COUNT(*) FROM diagnoses  WHERE health_number LIKE 'DEMO-%'").fetchone()[0] > 0,
            con.execute("SELECT COUNT(*) FROM medications WHERE health_number LIKE 'DEMO-%'").fetchone()[0] > 0,
            con.execute("SELECT COUNT(*) FROM imaging    WHERE health_number LIKE 'DEMO-%'").fetchone()[0] > 0,
            con.execute("SELECT COUNT(*) FROM surgeries  WHERE health_number LIKE 'DEMO-%'").fetchone()[0] > 0,
        ]
        if all(checks):
            return
        logger.info("Re-seeding sub-tables for DEMO patients.")
    else:
        logger.info("Seeding %d missing DEMO patients (found %d/30).", 30 - demo_count, demo_count)

    # ------------------------------------------------------------------ PATIENTS
    rows = [
        ("DEMO-DE-001","Klaus","Müller","1958-04-12","Male","A+","DE","de-DE",
         "k.mueller@email.de","+49 711 100 1001","Königstraße 12, 70173 Stuttgart",
         "Greta Müller","+49 711 100 2001","AOK-BW 111222333","Dr. Hans Becker",
         178.0,84.0,"Known CAD, hypertension, hyperlipidaemia. Statins + ACE inhibitor.",
         "Ex-smoker (30 pack-years, quit 2010)","Occasional (1-2 drinks/week)",
         "Retired mechanical engineer","Married",
         "Father: MI at 55. Mother: Hypertension. Brother: T2DM.",
         "Lives with wife. Two adult children nearby. Walks 30 min/day.",
         "Stable mood. Mild health anxiety related to cardiac history.",
         "Independent ADLs. Drives. NYHA I."),
        ("DEMO-DE-002","Anna","Schneider","1985-07-23","Female","O+","DE","de-DE",
         "a.schneider@email.de","+49 89 200 2002","Maximilianstraße 5, 80539 München",
         "Thomas Schneider","+49 89 200 3002","TK 444555666","Dr. Maria Fischer",
         165.0,61.0,"Type 1 diabetes since age 12. Insulin pump user.",
         "Never smoker","None",
         "Graphic designer (self-employed)","Single",
         "Mother: T1DM. Maternal aunt: Hashimoto thyroiditis.",
         "Lives alone. Regular gym 3x/week. Certified carb counting.",
         "Well-adjusted. Occasional frustration with pump alarms.",
         "Fully independent. Works full-time."),
        ("DEMO-DE-003","Heinrich","Weber","1971-11-05","Male","B+","DE","de-DE",
         "h.weber@email.de","+49 30 300 3003","Unter den Linden 22, 10117 Berlin",
         "Sabine Weber","+49 30 300 4003","Barmer 777888999","Dr. Ute Hoffmann",
         181.0,91.0,"COPD stage 2, ex-smoker 10 years.",
         "Ex-smoker (25 pack-years, quit 2016)","Moderate (3-4 beers/week)",
         "Bus driver (on sick leave)","Married",
         "Father: COPD. Mother: Lung cancer (deceased 2015).",
         "Lives with wife and teenage son. Low activity due to dyspnoea.",
         "Depressed mood since diagnosis. On watchful waiting.",
         "Mild-moderate limitation. Cannot climb >1 flight without stopping."),
        ("DEMO-DE-004","Sophie","Fischer","1992-03-14","Female","AB+","DE","de-DE",
         "s.fischer@email.de","+49 40 400 4004","Alsterchaussee 8, 20149 Hamburg",
         "Markus Fischer","+49 40 400 5004","DAK 222333444","Dr. Peter Braun",
         168.0,58.0,"Migraines with aura. Topiramate prophylaxis.",
         "Never smoker","Minimal (occasional wine)",
         "Junior lawyer","In a relationship",
         "Mother: Migraines. Maternal grandmother: Stroke at 72.",
         "High-stress job. Poor sleep hygiene. Skips meals frequently.",
         "Anxiety about migraine triggers at work.",
         "Fully functional between attacks. Misses avg 2 days/month."),
        ("DEMO-DE-005","Wolfgang","Bauer","1945-09-30","Male","O-","DE","de-DE",
         "w.bauer@email.de","+49 221 500 5005","Domstraße 3, 50667 Köln",
         "Ingrid Bauer","+49 221 500 6005","AOK 333444555","Dr. Klaus Richter",
         175.0,79.0,"Atrial fibrillation on anticoagulation. Pacemaker 2018.",
         "Ex-smoker (15 pack-years, quit 1995)","None",
         "Retired teacher","Married",
         "Father: AF and stroke. Mother: Heart failure.",
         "Lives with wife. Minimal physical activity. No driving since pacemaker.",
         "Resigned but cooperative. Concerned about bleeding risk.",
         "Moderate limitation. Needs reminders for INR checks."),
        ("DEMO-DE-006","Lena","Wagner","2000-01-18","Female","A-","DE","de-DE",
         "l.wagner@email.de","+49 69 600 6006","Zeil 15, 60313 Frankfurt",
         "Petra Wagner","+49 69 600 7006","IKK 555666777","Dr. Andrea Schäfer",
         170.0,55.0,"Anaphylaxis history to bee stings. EpiPen carrier.",
         "Never smoker","None",
         "University student (biology)","Single",
         "No known family allergies. Father: Eczema.",
         "Active outdoors (hiking, cycling). Vigilant about EpiPen. MedicAlert bracelet.",
         "Mild anxiety regarding accidental exposure.",
         "Fully independent. Active lifestyle."),
        ("DEMO-DE-007","Thomas","Becker","1963-06-22","Male","B-","DE","de-DE",
         "t.becker@email.de","+49 511 700 7007","Leinstraße 9, 30159 Hannover",
         "Claudia Becker","+49 511 700 8007","HEK 666777888","Dr. Bernd König",
         183.0,96.0,"T2DM, obesity BMI 32.5. Metformin + empagliflozin.",
         "Current smoker (10 cigarettes/day)","Moderate (beer, weekends)",
         "Warehouse manager","Married",
         "Father: T2DM, MI. Mother: Obesity, hypertension.",
         "Sedentary job. Irregular meal times. Financially stressed.",
         "Resistant to lifestyle changes. Ambivalent about smoking cessation.",
         "Functional but tires easily. BMI 32.5."),
        ("DEMO-DE-008","Mia","Schmitt","1998-12-03","Female","O+","DE","de-DE",
         "m.schmitt@email.de","+49 341 800 8008","Augustusplatz 1, 04109 Leipzig",
         "Jan Schmitt","+49 341 800 9008","BKK 888999000","Dr. Eva Lehmann",
         163.0,52.0,"Moderate persistent asthma. ICS + SABA.",
         "Never smoker","None",
         "Student nurse","Single",
         "Mother: Asthma. Father: Allergic rhinitis.",
         "Active. Cat allergy (avoids). Carries rescue inhaler at all times.",
         "Good insight into triggers. Mildly anxious during exacerbations.",
         "Fully active. Occasional exercise-induced wheeze."),
        ("DEMO-DE-009","Franz","Kraus","1952-08-17","Male","A+","DE","de-DE",
         "f.kraus@email.de","+49 911 900 9009","Kaiserstraße 4, 90403 Nürnberg",
         "Helga Kraus","+49 911 900 0009","VdAK 100200300","Dr. Dieter Wolf",
         177.0,88.0,"CKD stage 3, gout, hyperuricaemia.",
         "Ex-smoker (20 pack-years, quit 2005)","Occasional",
         "Retired pharmacist","Married",
         "Father: CKD. Brother: Gout.",
         "Swimming 2x/week. Good medication knowledge. Low-purine diet.",
         "Calm and well-informed. Proactive about follow-ups.",
         "Independent. Some ankle swelling on prolonged standing."),
        ("DEMO-DE-010","Emma","Zimmermann","1975-05-09","Female","AB-","DE","de-DE",
         "e.zimm@email.de","+49 431 010 0110","Holstenstraße 1, 24103 Kiel",
         "Paul Zimmermann","+49 431 010 0220","Knappschaft 400500600","Dr. Renate Alt",
         162.0,67.0,"Hypothyroidism on levothyroxine.",
         "Never smoker","Occasional (1-2 glasses wine/week)",
         "High school teacher","Married",
         "Mother: Hypothyroidism, T2DM. Sister: Hashimoto thyroiditis.",
         "Active. Yoga 3x/week. Takes levothyroxine consistently in the morning.",
         "Stable mood. Occasionally fatigued prior to TSH review.",
         "Fully functional."),
        ("DEMO-TR-001","Ahmet","Yılmaz","1965-03-10","Male","B+","TR","tr-TR",
         "a.yilmaz@email.com","+90 212 111 1001","Bağcılar Mah. No:5, 34200 İstanbul",
         "Fatma Yılmaz","+90 532 111 2001","SGK-5512873690","Dr. Mehmet Kaya",
         174.0,87.0,"T2DM, hypertension, microalbuminuria. Metformin + amlodipine.",
         "Current smoker (1 pack/day for 25 years)","Rarely",
         "Taxi driver","Married",
         "Father: T2DM, stroke. Mother: Hypertension. Brother: MI at 50.",
         "Sedentary job (driving 10h/day). High-carbohydrate diet. Irregular meals.",
         "Frustrated with disease progression. Denies need for insulin.",
         "Functional but fatigues quickly. Nocturia x3/night."),
        ("DEMO-TR-002","Fatma","Kaya","1978-11-25","Female","A+","TR","tr-TR",
         "f.kaya@email.com","+90 312 222 2002","Atatürk Blv. No:22, 06100 Ankara",
         "Ali Kaya","+90 533 222 3002","SGK-6623984701","Dr. Zeynep Acar",
         160.0,63.0,"Rheumatoid arthritis. MTX + hydroxychloroquine.",
         "Never smoker","None",
         "Primary school teacher","Married",
         "Mother: RA. Aunt: SLE.",
         "Active within pain limits. Morning stiffness ~30 min. Supportive husband.",
         "Adapted well. Mild depression in flare periods.",
         "Mild functional limitation during flares. Independent between episodes."),
        ("DEMO-TR-003","Mustafa","Demir","1950-07-04","Male","O+","TR","tr-TR",
         "m.demir@email.com","+90 232 333 3003","Konak Mah. No:8, 35250 İzmir",
         "Ayşe Demir","+90 534 333 4003","SGK-7734095812","Dr. Hasan Çelik",
         170.0,78.0,"Ischaemic heart disease post-CABG 2015. Aspirin + statin + beta-blocker.",
         "Ex-smoker (35 pack-years, quit 2015)","None",
         "Retired civil servant","Married",
         "Father: MI (deceased). Two brothers: CAD.",
         "Cardiac rehab completed. Daily walks 20 min. Mediterranean diet.",
         "Cautious but positive. Fearful of another cardiac event.",
         "Moderate limitation. NYHA II. No chest pain at rest."),
        ("DEMO-TR-004","Zeynep","Şahin","1990-02-14","Female","AB+","TR","tr-TR",
         "z.sahin@email.com","+90 224 444 4004","Nilüfer Mah. No:3, 16110 Bursa",
         "Can Şahin","+90 535 444 5004","SGK-8845206923","Dr. Seda Öztürk",
         164.0,57.0,"Epilepsy, seizure-free 3 years. Levetiracetam.",
         "Never smoker","None",
         "Accountant","Married",
         "No family history of epilepsy. Mother: Migraine.",
         "Avoids alcohol and sleep deprivation. Does not drive per neurology advice.",
         "Anxious about seizure recurrence. Good medication compliance.",
         "Fully functional. Uses public transport."),
        ("DEMO-TR-005","Mehmet","Çelik","1972-09-19","Male","A-","TR","tr-TR",
         "m.celik@email.com","+90 322 555 5005","Seyhan Mah. No:11, 01250 Adana",
         "Emine Çelik","+90 536 555 6005","SGK-9956317034","Dr. Kamil Arslan",
         180.0,95.0,"COPD, chronic smoker. Tiotropium inhaler.",
         "Current smoker (2 packs/day for 30 years)","Moderate",
         "Construction site supervisor","Married",
         "Father: COPD (deceased). Mother: Asthma.",
         "Physically demanding work. Refuses to stop smoking.",
         "Resistant to smoking cessation. Minimises symptoms.",
         "Moderate limitation. Dyspnoea on moderate exertion. FEV1 58%."),
        ("DEMO-TR-006","Ayşe","Arslan","1985-06-30","Female","B-","TR","tr-TR",
         "a.arslan@email.com","+90 462 666 6006","Ortahisar Mah. No:7, 61080 Trabzon",
         "Kemal Arslan","+90 537 666 7006","SGK-1067428145","Dr. Necla Doğan",
         157.0,54.0,"Hashimoto thyroiditis. Levothyroxine 75mcg.",
         "Never smoker","None",
         "Pharmacist","Married",
         "Mother: Hypothyroidism. Sister: Graves' disease.",
         "Good health literacy. Takes medication consistently.",
         "Stable. Mild fatigue if dose suboptimal.",
         "Fully functional."),
        ("DEMO-TR-007","Ali","Doğan","1958-12-08","Male","O-","TR","tr-TR",
         "a.dogan@email.com","+90 332 777 7007","Meram Mah. No:14, 42250 Konya",
         "Hatice Doğan","+90 538 777 8007","SGK-2178539256","Dr. Bilal Yıldız",
         172.0,82.0,"Prostate cancer post-prostatectomy 2020. PSA monitoring.",
         "Never smoker","None",
         "Retired imam","Married",
         "Brother: Prostate cancer at 62.",
         "Supported by family. Religious coping. Regular PSA follow-up.",
         "Accepting of diagnosis. Mild anxiety at PSA test times.",
         "Independent. Mild urinary urgency."),
        ("DEMO-TR-008","Elif","Yıldız","2002-04-22","Female","A+","TR","tr-TR",
         "e.yildiz@email.com","+90 242 888 8008","Muratpaşa Mah. No:6, 07160 Antalya",
         "Hüseyin Yıldız","+90 539 888 9008","SGK-3289640367","Dr. Aylin Koç",
         166.0,50.0,"Iron-deficiency anaemia. Ferrous sulfate.",
         "Never smoker","None",
         "University student (nursing)","Single",
         "Mother: Iron-deficiency anaemia.",
         "Vegetarian diet. Heavy menstrual periods. Good medication adherence.",
         "Fatigued but motivated. Good insight.",
         "Functional. Mild exertional fatigue."),
        ("DEMO-TR-009","İbrahim","Koç","1944-01-15","Male","AB+","TR","tr-TR",
         "i.koc@email.com","+90 362 999 9009","İlkadım Mah. No:19, 55090 Samsun",
         "Nuriye Koç","+90 530 999 0009","SGK-4390751478","Dr. Ercan Başar",
         168.0,73.0,"Parkinson disease, mild stage. Levodopa/carbidopa.",
         "Never smoker","None",
         "Retired fisherman","Married",
         "No family history of Parkinson. Father: Dementia.",
         "Wife provides daily support. Physiotherapy 2x/week.",
         "Accepting of limitations. Mildly low mood on difficult days.",
         "Mild tremor at rest. Independent with supervision for complex ADLs."),
        ("DEMO-TR-010","Hatice","Öztürk","1968-08-07","Female","O+","TR","tr-TR",
         "h.ozturk@email.com","+90 212 010 0110","Kadıköy Mah. No:2, 34710 İstanbul",
         "Osman Öztürk","+90 531 010 0220","SGK-5401862589","Dr. Serkan Erdoğan",
         158.0,70.0,"Osteoporosis. Calcium, vitamin D, bisphosphonate.",
         "Never smoker","None",
         "Retired nurse","Married",
         "Mother: Hip fracture at 70. Sister: Osteoporosis.",
         "Daily walks. Calcium-rich diet. Fall prevention measures at home.",
         "Compliant and informed. Worried about fracture risk.",
         "Fully independent. Cautious on stairs."),
        ("DEMO-UK-001","James","Wilson","1955-06-15","Male","O+","UK","en-GB",
         "j.wilson@nhs.uk","+44 7700 100 001","14 Baker Street, London W1U 3BW",
         "Margaret Wilson","+44 7700 200 001","NHS-111222333","Dr. Sarah Thompson",
         176.0,86.0,"Ischaemic heart disease, heart failure EF 40%. Furosemide + bisoprolol + ramipril.",
         "Ex-smoker (40 pack-years, quit 2005)","None",
         "Retired police officer","Married",
         "Father: MI at 60. Mother: Hypertension. Brother: Bypass surgery.",
         "Sedentary since HF diagnosis. Wife helps with household tasks.",
         "Low mood linked to reduced independence. Open to CBT referral.",
         "Moderate limitation. NYHA II-III. Breathless on stairs."),
        ("DEMO-UK-002","Emily","Clarke","1988-11-05","Female","O-","UK","en-GB",
         "e.clarke@nhs.uk","+44 7700 100 002","22 Oxford Street, London W1D 1AN",
         "James Clarke","+44 7700 200 002","NHS-222333444","Dr. Peter Hall",
         168.0,62.0,"Moderate asthma. Seretide + Ventolin. History of status asthmaticus.",
         "Never smoker","Occasional (social)",
         "Marketing manager","Married",
         "Mother: Asthma. Father: Eczema. Sister: Allergic rhinitis.",
         "Identifies triggers: cold air, exercise, stress. Written asthma action plan.",
         "Anxious post-HDU admission. Improved compliance since.",
         "Functional. Avoids high-intensity exercise unsupervised."),
        ("DEMO-UK-003","Robert","Johnson","1945-02-28","Male","A+","UK","en-GB",
         "r.johnson@nhs.uk","+44 7700 100 003","45 Princes Street, Edinburgh EH2 2BJ",
         "Dorothy Johnson","+44 7700 200 003","NHS-333444555","Dr. Fiona MacDonald",
         180.0,84.0,"COPD + hypertension + T2DM. Multiple inhalers, metformin, amlodipine.",
         "Ex-smoker (50 pack-years, quit 2012)","None",
         "Retired carpenter","Widower",
         "Wife died of cancer 2021. Son and daughter supportive.",
         "Lives alone since bereavement. Daughter visits twice weekly.",
         "Grief, mild depression. Refused antidepressants. Attends peer support group.",
         "Moderate limitation. Needs rest after 200m walking."),
        ("DEMO-UK-004","Charlotte","Brown","1992-08-11","Female","B+","UK","en-GB",
         "c.brown@nhs.uk","+44 7700 100 004","8 Royal Mile, Edinburgh EH1 2PB",
         "David Brown","+44 7700 200 004","NHS-444555666","Dr. Gordon Reid",
         165.0,58.0,"Crohn's disease on azathioprine. Annual colonoscopy.",
         "Never smoker","None",
         "Junior doctor (FY2)","Single",
         "Father: Crohn's disease. Uncle: Ulcerative colitis.",
         "High-stress profession. Low-residue diet during flares. IBD nurse support.",
         "Copes well professionally. Embarrassed discussing bowel symptoms.",
         "Functional in remission. Flares 1-2x/year."),
        ("DEMO-UK-005","William","Taylor","1960-04-03","Male","AB+","UK","en-GB",
         "w.taylor@nhs.uk","+44 7700 100 005","33 Deansgate, Manchester M3 4LF",
         "Susan Taylor","+44 7700 200 005","NHS-555666777","Dr. Angela Patel",
         182.0,92.0,"Hypertension, gout. Losartan, allopurinol.",
         "Ex-smoker (20 pack-years, quit 2000)","Moderate (pub, weekends)",
         "Accountant","Married",
         "Father: Hypertension, gout. Mother: T2DM.",
         "Moderate activity. Follows low-purine diet incompletely.",
         "Cooperative but inconsistent with diet advice.",
         "Fully functional. Gout flares 2-3x/year."),
        ("DEMO-UK-006","Olivia","Martin","2001-09-17","Female","A-","UK","en-GB",
         "o.martin@nhs.uk","+44 7700 100 006","7 Church Street, Birmingham B3 2NP",
         "Richard Martin","+44 7700 200 006","NHS-666777888","Dr. Kevin Sharma",
         162.0,54.0,"Type 1 diabetes. Insulin pump + CGM. HbA1c 7.1%.",
         "Never smoker","None",
         "University student (economics)","Single",
         "Father: T1DM. Maternal aunt: Hypothyroidism.",
         "Motivated. Attends young adult diabetes group. Good CGM use.",
         "Positive outlook. Mild distress during HbA1c spikes.",
         "Fully independent. Active."),
        ("DEMO-UK-007","George","White","1970-07-22","Male","B-","UK","en-GB",
         "g.white@nhs.uk","+44 7700 100 007","19 Broad Street, Bristol BS1 2HP",
         "Helen White","+44 7700 200 007","NHS-777888999","Dr. Louise Fletcher",
         175.0,79.0,"Bipolar disorder. Lithium 800mg. Regular lithium levels.",
         "Ex-smoker (10 pack-years, quit 2010)","None (avoiding alcohol on lithium)",
         "Secondary school art teacher","Married",
         "Mother: Bipolar disorder type II. Brother: Depression.",
         "Stable. Wife alert to mood changes. Monthly psychiatry clinic.",
         "Euthymic. Good insight. Proactive about sleep hygiene.",
         "Fully functional. Works full-time."),
        ("DEMO-UK-008","Isabella","Davies","1983-12-01","Female","O+","UK","en-GB",
         "i.davies@nhs.uk","+44 7700 100 008","55 High Street, Cardiff CF10 1BB",
         "Thomas Davies","+44 7700 200 008","NHS-888999000","Dr. Rachel Evans",
         170.0,65.0,"Migraine + endometriosis. Sumatriptan PRN.",
         "Never smoker","Minimal",
         "Journalist","Married",
         "Mother: Endometriosis. Sister: Migraine.",
         "Stress and menstruation are major triggers. Uses pain diary.",
         "Coping well but frustrated by diagnostic delays for endometriosis.",
         "Functional. Dysmenorrhoea limits activity 2-3 days/month."),
        ("DEMO-UK-009","Henry","Moore","1938-03-19","Male","A+","UK","en-GB",
         "h.moore@nhs.uk","+44 7700 100 009","3 Castle Street, Leeds LS1 2HL",
         "Mary Moore","+44 7700 200 009","NHS-999000111","Dr. John Barker",
         171.0,75.0,"Aortic stenosis (moderate), AF on warfarin. Annual echo.",
         "Never smoker","None",
         "Retired university professor","Married",
         "Father: Aortic stenosis, valve replacement at 75. Mother: AF.",
         "Wife manages medications. Son reviews INR records. Minimal exercise.",
         "Alert and engaged. Anxious about valve progression.",
         "Mild limitation. NYHA I-II. Lives on ground floor."),
        ("DEMO-UK-010","Amelia","Garcia","1977-06-28","Female","AB-","UK","en-GB",
         "a.garcia@nhs.uk","+44 7700 010 010","12 Victoria Road, Liverpool L6 3AB",
         "Carlos Garcia","+44 7700 020 020","NHS-000111222","Dr. Natalie Osei",
         164.0,68.0,"SLE on hydroxychloroquine. Vitamin D deficiency.",
         "Never smoker","None",
         "NHS administrator","Married",
         "Mother: SLE. Aunt: Sjögren's syndrome.",
         "Avoids sun. Wears SPF 50 daily. Good medication adherence.",
         "Resilient. Occasional anxiety during flares.",
         "Functional between flares. Fatigue limits activity during active disease."),
    ]

    if demo_count < 30:
        con.executemany(
            """INSERT OR IGNORE INTO patients
               (health_number,first_name,last_name,date_of_birth,sex,blood_type,
                nationality,language,email,phone,address,emergency_name,emergency_phone,
                insurance_id,gp_name,height_cm,weight_kg,notes,
                smoking_status,alcohol_use,occupation,marital_status,
                family_history,social_history,mood_assessment,functional_status)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            rows
        )

    # ------------------------------------------------------------------ DIAGNOSES
    diags = [
        ("DEMO-DE-001","I25.10","Coronary artery disease","active","2018-05-20","Dr. Becker","Stable angina. LAD stent 2018."),
        ("DEMO-DE-001","I10","Essential hypertension","active","2015-03-10","Dr. Becker","Target BP <130/80. Currently 148/92 — uptitration considered."),
        ("DEMO-DE-001","E78.5","Hyperlipidaemia","active","2015-03-10","Dr. Becker","LDL 2.8 — above CVD target. Consider rosuvastatin switch."),
        ("DEMO-DE-002","E10.9","Type 1 diabetes mellitus","active","2002-09-05","Dr. Fischer","Insulin pump since 2015. HbA1c 7.2%."),
        ("DEMO-DE-003","J44.1","COPD stage 2","active","2016-07-12","Dr. Hoffmann","Tiotropium + LABA. FEV1 62% predicted. Declining."),
        ("DEMO-DE-004","G43.101","Migraine with aura","active","2019-04-22","Dr. Braun","Topiramate prophylaxis. 2-3 attacks/month."),
        ("DEMO-DE-005","I48.91","Persistent atrial fibrillation","active","2017-08-14","Dr. Richter","Rivaroxaban anticoagulation. Rate controlled."),
        ("DEMO-DE-005","Z95.0","Cardiac pacemaker in situ","active","2018-02-20","Dr. Richter","AAI pacemaker implanted 2018. Annual pacemaker clinic."),
        ("DEMO-DE-006","T78.2","Anaphylaxis — bee sting","active","2019-06-01","Dr. Schäfer","EpiPen x2 prescribed. Venom immunotherapy under consideration."),
        ("DEMO-DE-007","E11.9","Type 2 diabetes mellitus","active","2014-11-03","Dr. König","HbA1c 7.8%. Metformin + empagliflozin."),
        ("DEMO-DE-007","E66.01","Obesity","active","2014-11-03","Dr. König","BMI 32.5. Dietitian referral made."),
        ("DEMO-DE-008","J45.30","Moderate persistent asthma","active","2011-03-08","Dr. Lehmann","ICS + SABA. Triggers: cats, cold air, exercise."),
        ("DEMO-DE-009","N18.3","Chronic kidney disease stage 3b","active","2019-09-18","Dr. Wolf","eGFR 42. Nephrology review scheduled. Avoid nephrotoxins."),
        ("DEMO-DE-009","M10.9","Gout","active","2020-04-05","Dr. Wolf","Allopurinol 300mg. Uric acid 520 µmol/L — dose review needed."),
        ("DEMO-DE-010","E03.9","Hypothyroidism","active","2013-06-15","Dr. Alt","Levothyroxine 75mcg. TSH 2.1 — well controlled."),
        ("DEMO-TR-001","E11.9","Type 2 diabetes mellitus","active","2014-04-12","Dr. Kaya","HbA1c 8.2%. Poorly controlled. Insulin initiation discussed."),
        ("DEMO-TR-001","I10","Essential hypertension","active","2016-08-03","Dr. Kaya","BP 158/98 on amlodipine 5mg. Uptitration or add-on needed."),
        ("DEMO-TR-001","N08","Diabetic nephropathy","active","2022-11-19","Dr. Özdemir","Microalbuminuria 48 mg/g. ACE inhibitor added."),
        ("DEMO-TR-002","M05.80","Rheumatoid arthritis, seropositive","active","2012-03-07","Dr. Acar","MTX 15mg/week + HCQ. DAS28 2.8 at last review."),
        ("DEMO-TR-003","I25.10","CAD post-CABG 2015","active","2015-01-20","Dr. Çelik","Triple vessel CABG. NSTEMI 2025 — stent to mid-LAD."),
        ("DEMO-TR-004","G40.909","Epilepsy, focal onset","active","2018-07-14","Dr. Öztürk","Seizure-free 3 years on levetiracetam 500mg BD."),
        ("DEMO-TR-005","J44.1","COPD GOLD II","active","2017-05-09","Dr. Arslan","FEV1 58%. Tiotropium. Active smoker — cessation counselled."),
        ("DEMO-TR-006","E06.3","Hashimoto thyroiditis","active","2016-09-22","Dr. Doğan","TPO antibodies positive. Levothyroxine 75mcg."),
        ("DEMO-TR-007","C61","Prostate cancer, post-prostatectomy","active","2019-03-10","Dr. Yıldız","Radical prostatectomy 2020. PSA <0.1 ng/mL. Biochemical remission."),
        ("DEMO-TR-008","D50.9","Iron-deficiency anaemia","active","2023-02-18","Dr. Koç","Hb 9.8 g/dL at dx. Now 10.2 on ferrous sulfate. Heavy menses."),
        ("DEMO-TR-009","G20","Parkinson disease, mild","active","2020-11-05","Dr. Başar","Hoehn-Yahr stage 2. Co-careldopa TID. Physiotherapy."),
        ("DEMO-TR-010","M81.0","Postmenopausal osteoporosis","active","2018-04-12","Dr. Erdoğan","T-score -2.8. Alendronate + calcium/VitD."),
        ("DEMO-UK-001","I25.10","Ischaemic heart disease","active","2016-09-14","Dr. Thompson","Stable on maximal medical therapy."),
        ("DEMO-UK-001","I50.9","Heart failure with reduced EF (40%)","active","2020-03-22","Dr. Thompson","NYHA II-III. NT-proBNP 1240 pg/mL."),
        ("DEMO-UK-002","J45.20","Moderate asthma","active","2005-03-22","Dr. Hall","Well-controlled. History of status asthmaticus 2025."),
        ("DEMO-UK-003","J44.1","COPD GOLD II","active","2012-06-08","Dr. MacDonald","Triple inhaler therapy. FEV1/FVC <70%."),
        ("DEMO-UK-003","E11.9","Type 2 diabetes mellitus","active","2015-01-20","Dr. MacDonald","HbA1c 7.2%. Metformin 500mg BD."),
        ("DEMO-UK-004","K50.90","Crohn's disease, ileocolonic","active","2014-07-09","Dr. Reid","In remission on azathioprine. Annual colonoscopy."),
        ("DEMO-UK-005","I10","Essential hypertension","active","2011-08-12","Dr. Patel","Controlled on losartan 100mg."),
        ("DEMO-UK-005","M10.9","Gout","active","2018-02-28","Dr. Patel","Allopurinol 300mg. Flare frequency reducing."),
        ("DEMO-UK-006","E10.9","Type 1 diabetes mellitus","active","2015-11-03","Dr. Sharma","Insulin pump + CGM. HbA1c 7.1%."),
        ("DEMO-UK-007","F31.9","Bipolar affective disorder","active","2001-05-18","Dr. Fletcher","Stable on lithium 800mg BD. Euthymic."),
        ("DEMO-UK-008","G43.909","Migraine without aura","active","2010-09-30","Dr. Evans","3-4 attacks/month. Sumatriptan PRN."),
        ("DEMO-UK-008","N80.9","Endometriosis, stage II","active","2016-03-14","Dr. Evans","OCP for hormonal suppression. Laparoscopy 2016."),
        ("DEMO-UK-009","I35.0","Aortic stenosis, moderate","active","2019-12-10","Dr. Barker","Mean gradient 28 mmHg. Annual echocardiogram surveillance."),
        ("DEMO-UK-009","I48.91","Atrial fibrillation","active","2017-06-05","Dr. Barker","Warfarin anticoagulation. INR target 2-3."),
        ("DEMO-UK-010","M32.9","Systemic lupus erythematosus","active","2009-08-24","Dr. Osei","No major organ involvement. HCQ 400mg."),
        ("DEMO-UK-010","E55.9","Vitamin D deficiency","active","2022-01-10","Dr. Osei","25-OH-VitD 32 nmol/L. Supplementing with colecalciferol."),
    ]
    con.executemany(
        "INSERT OR IGNORE INTO diagnoses (health_number,icd_code,description,status,diagnosed_date,diagnosing_doctor,notes) VALUES (?,?,?,?,?,?,?)",
        diags
    )

    # ------------------------------------------------------------------ MEDICATIONS
    meds = [
        ("DEMO-DE-001","Atorvastatin 40mg","40mg","Once daily at night","2018-05-25",None,"Dr. Becker","active","Mild myalgia (CK checked — normal)","Good"),
        ("DEMO-DE-001","Ramipril 5mg","5mg","Once daily morning","2015-03-15",None,"Dr. Becker","active","Dry cough — patient tolerating","Good"),
        ("DEMO-DE-001","Aspirin 100mg","100mg","Once daily with food","2018-05-25",None,"Dr. Becker","active","Mild GI discomfort (takes with food, improved)","Good"),
        ("DEMO-DE-001","Bisoprolol 5mg","5mg","Once daily morning","2020-01-10",None,"Dr. Becker","active","Mild fatigue on exertion","Good"),
        ("DEMO-DE-002","Insulin pump — NovoRapid","variable basal+bolus","Continuous subcutaneous","2015-09-01",None,"Dr. Fischer","active","Occasional nocturnal hypoglycaemia","Excellent — certified pump user, carb counting"),
        ("DEMO-DE-003","Tiotropium 18mcg HandiHaler","18mcg","Once daily inhaled (morning)","2016-07-20",None,"Dr. Hoffmann","active","Dry mouth","Good — correct inhaler technique confirmed"),
        ("DEMO-DE-003","Salmeterol/Fluticasone 50/250","2 puffs","Twice daily inhaled","2016-07-20",None,"Dr. Hoffmann","active","None reported","Good"),
        ("DEMO-DE-004","Sumatriptan 50mg","50mg (max 100mg/attack)","PRN at migraine onset","2019-04-25",None,"Dr. Braun","active","Transient chest tightness (warned)","Appropriate PRN use"),
        ("DEMO-DE-004","Topiramate 25mg","25mg (titrating to 50mg)","Once daily","2022-03-01",None,"Dr. Braun","active","Mild cognitive slowing, word-finding difficulty","Partially adherent — dose review at next visit"),
        ("DEMO-DE-005","Rivaroxaban 20mg","20mg","Once daily with evening meal","2017-08-20",None,"Dr. Richter","active","Occasional bruising","Excellent compliance"),
        ("DEMO-DE-006","Epinephrine EpiPen 0.3mg","0.3mg","IM injection for anaphylaxis","2019-06-05",None,"Dr. Schäfer","active","N/A — emergency use only","Carries at all times. Technique re-trained annually."),
        ("DEMO-DE-007","Metformin 1000mg","1000mg","Twice daily with meals","2014-11-10",None,"Dr. König","active","GI bloating initially — improved with slow titration","Moderate — sometimes skips evening dose"),
        ("DEMO-DE-007","Empagliflozin 10mg","10mg","Once daily morning","2020-06-15",None,"Dr. König","active","One episode genital candidiasis (treated topically)","Good"),
        ("DEMO-DE-008","Budesonide/Formoterol 200/6mcg","2 puffs","Twice daily — SMART therapy","2011-03-15",None,"Dr. Lehmann","active","Hoarseness (instructed to rinse mouth after use)","Good — SMART technique demonstrated"),
        ("DEMO-DE-008","Salbutamol 100mcg","2 puffs","PRN — max 8 puffs/day","2011-03-15",None,"Dr. Lehmann","active","Tremor at high doses (rare)","PRN use appropriate — not overusing"),
        ("DEMO-DE-009","Allopurinol 300mg","300mg","Once daily","2020-04-10",None,"Dr. Wolf","active","None reported","Good"),
        ("DEMO-DE-009","Ramipril 2.5mg","2.5mg","Once daily","2019-09-25",None,"Dr. Wolf","active","None","Good"),
        ("DEMO-DE-010","Levothyroxine 75mcg","75mcg","Once daily — fasting, 30 min before food","2013-06-20",None,"Dr. Alt","active","None at current dose","Excellent — consistent morning routine"),
        ("DEMO-TR-001","Metformin 1000mg","1000mg","Twice daily with meals","2014-04-15",None,"Dr. Kaya","active","GI discomfort initially, resolved","Moderate — skips doses on busy driving days"),
        ("DEMO-TR-001","Amlodipine 5mg","5mg","Once daily","2016-08-10",None,"Dr. Kaya","active","Mild bilateral ankle oedema","Good"),
        ("DEMO-TR-001","Ramipril 5mg","5mg","Once daily","2022-11-20",None,"Dr. Özdemir","active","Dry cough (tolerating)","Good"),
        ("DEMO-TR-001","Aspirin 100mg","100mg","Once daily","2017-01-05",None,"Dr. Kaya","active","None","Good"),
        ("DEMO-TR-002","Methotrexate 15mg","15mg","Once weekly (Monday)","2012-03-15",None,"Dr. Acar","active","Nausea day after dose (controlled with folic acid)","Good"),
        ("DEMO-TR-002","Hydroxychloroquine 400mg","400mg","Once daily","2012-03-15",None,"Dr. Acar","active","None reported","Excellent"),
        ("DEMO-TR-002","Folic acid 5mg","5mg","6 days/week (all days except MTX day)","2012-03-15",None,"Dr. Acar","active","None","Good — understands schedule"),
        ("DEMO-TR-003","Aspirin 100mg","100mg","Once daily","2015-01-25",None,"Dr. Çelik","active","None","Excellent"),
        ("DEMO-TR-003","Ticagrelor 90mg","90mg","Twice daily (post-NSTEMI 2025, 12 months DAPT)","2025-09-18",None,"Dr. Çelik","active","Dyspnoea (monitored)","Good — informed about DAPT importance"),
        ("DEMO-TR-003","Bisoprolol 5mg","5mg","Once daily","2015-01-25",None,"Dr. Çelik","active","Fatigue in first month — resolved","Good"),
        ("DEMO-TR-003","Rosuvastatin 20mg","20mg","Once daily at night","2015-01-25",None,"Dr. Çelik","active","Mild myalgia — CK normal","Good"),
        ("DEMO-TR-004","Levetiracetam 500mg","500mg","Twice daily","2018-07-20",None,"Dr. Öztürk","active","Mild mood irritability in first 3 months (improving)","Excellent — no missed doses"),
        ("DEMO-TR-005","Tiotropium 18mcg","18mcg","Once daily inhaled","2017-05-15",None,"Dr. Arslan","active","Dry mouth","Partial — forgets at weekends"),
        ("DEMO-TR-006","Levothyroxine 75mcg","75mcg","Once daily morning fasting","2016-09-28",None,"Dr. Doğan","active","None at current dose","Excellent"),
        ("DEMO-TR-007","Tamsulosin 400mcg","400mcg","Once daily after evening meal","2020-01-15",None,"Dr. Yıldız","active","Mild orthostatic dizziness initially (resolved)","Good"),
        ("DEMO-TR-008","Ferrous sulfate 200mg","200mg","Twice daily with food","2023-02-22",None,"Dr. Koç","active","Constipation, dark stools (warned)","Good — high-fibre diet advised"),
        ("DEMO-TR-009","Co-careldopa 125mg (100/25)","125mg","Three times daily","2020-11-10",None,"Dr. Başar","active","End-of-dose wearing off — timing adjusted","Good — wife supervises administration"),
        ("DEMO-TR-010","Alendronic acid 70mg","70mg","Once weekly — fasting, remain upright 30 min","2018-04-18",None,"Dr. Erdoğan","active","Mild oesophageal discomfort initially (technique reinforced)","Good"),
        ("DEMO-TR-010","Calcium carbonate + Vit D3 1200mg/800IU","1 tablet","Twice daily with meals","2018-04-18",None,"Dr. Erdoğan","active","Mild constipation (manageable)","Good"),
        ("DEMO-UK-001","Furosemide 40mg","40mg","Once daily morning","2020-03-25",None,"Dr. Thompson","active","Electrolytes monitored. Nocturia reduced by AM dosing.","Good — weighs daily, dose titrated by weight"),
        ("DEMO-UK-001","Bisoprolol 5mg","5mg","Once daily","2020-03-25",None,"Dr. Thompson","active","Fatigue","Good"),
        ("DEMO-UK-001","Ramipril 10mg","10mg","Once daily","2020-03-25",None,"Dr. Thompson","active","Dry cough — accepting","Good"),
        ("DEMO-UK-001","Atorvastatin 80mg","80mg","Once daily at night","2016-09-20",None,"Dr. Thompson","active","None reported","Excellent"),
        ("DEMO-UK-002","Salmeterol/Fluticasone 50/250","2 puffs","Twice daily","2015-04-01",None,"Dr. Hall","active","One episode oral candidiasis (treated with nystatin — rinse now consistent)","Good"),
        ("DEMO-UK-002","Salbutamol 100mcg","2 puffs","PRN — max 8 puffs/day","2005-03-25",None,"Dr. Hall","active","Tremor at high doses (rare)","Appropriate PRN use — not overusing"),
        ("DEMO-UK-003","Metformin 500mg","500mg","Twice daily with meals","2015-01-25",None,"Dr. MacDonald","active","Minimal GI side effects","Good"),
        ("DEMO-UK-003","Amlodipine 5mg","5mg","Once daily","2013-04-20",None,"Dr. MacDonald","active","Ankle swelling (mild)","Good"),
        ("DEMO-UK-003","Tiotropium 18mcg","18mcg","Once daily inhaled","2012-06-15",None,"Dr. MacDonald","active","Dry mouth","Good"),
        ("DEMO-UK-004","Azathioprine 100mg","100mg","Once daily","2014-07-15",None,"Dr. Reid","active","Nausea initially — resolved. FBC monitored 3-monthly.","Excellent"),
        ("DEMO-UK-005","Losartan 100mg","100mg","Once daily","2011-08-20",None,"Dr. Patel","active","None","Excellent"),
        ("DEMO-UK-005","Allopurinol 300mg","300mg","Once daily","2018-03-05",None,"Dr. Patel","active","None","Good"),
        ("DEMO-UK-006","Insulin NovoRapid (pump)","variable basal+bolus","Continuous subcutaneous","2019-05-01",None,"Dr. Sharma","active","Infusion site reactions — rotating sites as advised","Excellent — uses CGM alerts effectively"),
        ("DEMO-UK-007","Lithium carbonate 400mg","400mg","Twice daily","2001-06-01",None,"Dr. Fletcher","active","Mild tremor, mild polyuria — longstanding and acceptable","Excellent — never missed a dose in 5 years"),
        ("DEMO-UK-008","Sumatriptan 100mg","100mg","PRN at migraine onset (max 2/24h)","2010-10-05",None,"Dr. Evans","active","Mild chest tightness (warned, cardiac causes excluded)","Appropriate PRN use"),
        ("DEMO-UK-009","Warfarin","variable (INR-guided)","Daily — dose adjusted by anticoagulation clinic","2017-06-10",None,"Dr. Barker","active","Bruising. INR lability with dietary vitamin K changes.","Good — attends anticoagulation clinic monthly"),
        ("DEMO-UK-009","Atorvastatin 40mg","40mg","Once daily","2019-12-15",None,"Dr. Barker","active","No side effects reported","Good"),
        ("DEMO-UK-010","Hydroxychloroquine 400mg","400mg","Once daily with food","2009-09-01",None,"Dr. Osei","active","Mild GI discomfort (takes with food — improved)","Excellent — annual retinal screening up to date"),
        ("DEMO-UK-010","Colecalciferol 800 IU","800 IU","Once daily","2022-01-10",None,"Dr. Osei","active","None","Good"),
    ]
    con.executemany(
        "INSERT OR IGNORE INTO medications (health_number,name,dosage,frequency,start_date,end_date,prescribing_doctor,status,side_effects,adherence_notes) VALUES (?,?,?,?,?,?,?,?,?,?)",
        meds
    )

    # ------------------------------------------------------------------ VITALS
    vitals = [
        ("DEMO-DE-001","2026-02-01T09:00:00",148,92,76,97.8,36.6,84.0,178.0,26.5,5.2,16,2),
        ("DEMO-DE-002","2026-01-20T08:00:00",112,70,82,99.0,36.4,61.0,165.0,22.4,6.8,14,0),
        ("DEMO-DE-003","2026-02-10T11:00:00",138,84,88,93.0,36.8,91.0,181.0,27.7,4.9,22,3),
        ("DEMO-DE-004","2026-01-28T14:00:00",118,74,68,99.0,36.5,58.0,168.0,20.5,4.8,14,1),
        ("DEMO-DE-005","2026-02-05T09:30:00",132,80,62,97.0,36.4,79.0,175.0,25.8,5.1,16,1),
        ("DEMO-DE-006","2026-01-15T15:00:00",110,68,65,99.0,36.3,55.0,170.0,19.0,4.7,14,0),
        ("DEMO-DE-007","2026-02-12T10:00:00",144,90,84,97.5,36.7,96.0,183.0,28.7,7.4,17,2),
        ("DEMO-DE-008","2026-01-22T09:15:00",116,72,70,97.5,36.4,52.0,163.0,19.6,4.8,18,1),
        ("DEMO-DE-009","2026-02-08T08:45:00",152,94,78,95.5,36.6,88.0,177.0,28.1,5.3,16,2),
        ("DEMO-DE-010","2026-01-30T10:15:00",120,76,72,98.5,36.5,67.0,162.0,25.5,4.9,15,0),
        ("DEMO-TR-001","2026-02-15T11:30:00",158,98,86,96.8,37.0,87.0,174.0,28.7,9.2,18,3),
        ("DEMO-TR-002","2026-02-10T10:00:00",124,78,74,98.0,36.6,63.0,160.0,24.6,5.0,16,2),
        ("DEMO-TR-003","2026-01-25T09:00:00",136,84,70,96.0,36.7,78.0,170.0,27.0,5.2,17,1),
        ("DEMO-TR-004","2026-02-03T14:00:00",112,70,66,99.0,36.4,57.0,164.0,21.2,4.7,14,0),
        ("DEMO-TR-005","2026-02-18T09:30:00",138,86,92,91.0,36.9,95.0,180.0,29.3,5.1,24,4),
        ("DEMO-TR-006","2026-01-20T11:00:00",108,66,68,98.5,36.4,54.0,157.0,21.9,4.8,14,0),
        ("DEMO-TR-007","2026-02-05T09:00:00",126,78,72,98.0,36.5,82.0,172.0,27.7,5.0,15,1),
        ("DEMO-TR-008","2026-02-20T10:00:00",100,62,96,98.5,36.3,50.0,166.0,18.1,4.5,16,0),
        ("DEMO-TR-009","2026-01-28T09:30:00",118,72,68,97.5,36.6,73.0,168.0,25.9,5.1,16,1),
        ("DEMO-TR-010","2026-02-10T10:30:00",130,80,76,97.5,36.5,70.0,158.0,28.1,5.0,15,0),
        ("DEMO-UK-001","2026-02-12T10:00:00",142,88,68,96.5,36.6,86.0,176.0,27.7,5.3,18,2),
        ("DEMO-UK-002","2026-01-20T14:30:00",118,74,68,98.8,36.4,62.0,168.0,22.0,4.8,16,0),
        ("DEMO-UK-003","2026-02-08T09:00:00",144,90,82,92.5,36.8,84.0,180.0,25.9,6.8,22,3),
        ("DEMO-UK-004","2026-01-28T11:00:00",110,68,72,99.0,36.5,58.0,165.0,21.3,4.9,15,0),
        ("DEMO-UK-005","2026-02-15T10:00:00",148,92,78,97.5,36.6,92.0,182.0,27.8,5.1,16,1),
        ("DEMO-UK-006","2026-01-22T09:00:00",110,68,76,99.0,36.4,54.0,162.0,20.6,6.2,14,0),
        ("DEMO-UK-007","2026-02-10T14:30:00",122,76,70,98.5,36.5,79.0,175.0,25.8,4.9,15,0),
        ("DEMO-UK-008","2026-01-30T10:00:00",116,72,66,98.8,36.4,65.0,170.0,22.5,4.8,14,1),
        ("DEMO-UK-009","2026-02-05T09:00:00",136,82,74,97.0,36.6,75.0,171.0,25.6,5.2,17,1),
        ("DEMO-UK-010","2026-02-18T11:00:00",124,78,72,98.2,36.5,68.0,164.0,25.3,4.9,15,0),
    ]
    con.executemany(
        "INSERT OR IGNORE INTO vitals (health_number,recorded_at,bp_systolic,bp_diastolic,heart_rate,spo2,temperature,weight_kg,height_cm,bmi,glucose,respiratory_rate,pain_scale) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        vitals
    )

    # ------------------------------------------------------------------ LAB RESULTS
    labs = [
        ("DEMO-DE-001","HbA1c","5.4","%","< 5.7%","normal","2026-02-01","Labor Stuttgart","Dr. Becker","Non-diabetic range."),
        ("DEMO-DE-001","LDL Cholesterol","2.8","mmol/L","< 1.8 (CVD secondary prevention)","high","2026-02-01","Labor Stuttgart","Dr. Becker","Above target. Consider switch to rosuvastatin 40mg."),
        ("DEMO-DE-001","Troponin I","0.02","ng/mL","< 0.04","normal","2026-02-01","Labor Stuttgart","Dr. Becker","No acute myocardial injury."),
        ("DEMO-DE-001","eGFR","74","ml/min/1.73m²","≥ 60","normal","2026-02-01","Labor Stuttgart","Dr. Becker","Adequate renal function. Safe for ACE inhibitor."),
        ("DEMO-DE-001","CRP","3.2","mg/L","< 5.0","normal","2026-02-01","Labor Stuttgart","Dr. Becker","Mildly elevated — no acute infection identified."),
        ("DEMO-DE-001","Full Blood Count","WBC 6.8 / Hb 13.8 / PLT 210","mixed","Normal ranges","normal","2026-02-01","Labor Stuttgart","Dr. Becker","Normal haematology."),
        ("DEMO-DE-002","HbA1c","7.2","%","< 7.5% (T1DM NICE target)","normal","2026-01-20","Labor München","Dr. Fischer","Good control. Continue current pump settings."),
        ("DEMO-DE-002","TSH","2.4","mIU/L","0.4-4.0","normal","2026-01-20","Labor München","Dr. Fischer","Annual thyroid screen — euthyroid."),
        ("DEMO-DE-002","Fasting glucose","5.6","mmol/L","3.9-5.5","normal","2026-01-20","Labor München","Dr. Fischer","Within acceptable range pre-breakfast."),
        ("DEMO-DE-003","FEV1","62","% predicted","≥ 80%","low","2026-02-10","Lungenfunktion HH","Dr. Hoffmann","GOLD II. Decline from 65% last year — worsening trend."),
        ("DEMO-DE-003","FEV1/FVC ratio","0.58","ratio","≥ 0.70","low","2026-02-10","Lungenfunktion HH","Dr. Hoffmann","Fixed obstructive pattern confirmed post-bronchodilator."),
        ("DEMO-DE-003","ABG pH","7.38","","7.35-7.45","borderline","2026-02-10","Lungenfunktion HH","Dr. Hoffmann","PaO2 62, PaCO2 46 — mild type 1 respiratory failure at rest."),
        ("DEMO-DE-007","HbA1c","7.8","%","< 7.0% (T2DM target)","high","2026-02-12","Labor Hannover","Dr. König","Above target. Lifestyle re-counselled. Referral to dietitian."),
        ("DEMO-DE-007","Fasting glucose","8.4","mmol/L","< 7.0 (T2DM)","high","2026-02-12","Labor Hannover","Dr. König","Suboptimal. SGLT2 inhibitor dose review."),
        ("DEMO-DE-007","ALT","52","U/L","10-40","high","2026-02-12","Labor Hannover","Dr. König","Mildly elevated — NAFLD suspected. Abdominal ultrasound ordered."),
        ("DEMO-DE-007","Triglycerides","3.1","mmol/L","< 1.7","high","2026-02-12","Labor Hannover","Dr. König","Hypertriglyceridaemia — dietary advice reinforced."),
        ("DEMO-DE-009","eGFR","42","ml/min/1.73m²","≥ 60","low","2026-02-08","Labor Nürnberg","Dr. Wolf","CKD stage 3b. Nephrology referral pending."),
        ("DEMO-DE-009","Uric acid","520","µmol/L","< 360 (target on allopurinol)","high","2026-02-08","Labor Nürnberg","Dr. Wolf","Above target despite allopurinol. Dose increase to 400mg considered."),
        ("DEMO-DE-009","Creatinine","138","µmol/L","62-106","high","2026-02-08","Labor Nürnberg","Dr. Wolf","Consistent with CKD3b."),
        ("DEMO-DE-009","Potassium","4.8","mmol/L","3.5-5.0","normal","2026-02-08","Labor Nürnberg","Dr. Wolf","Upper normal. Monitor on ACE inhibitor."),
        ("DEMO-DE-010","TSH","2.1","mIU/L","0.4-4.0","normal","2026-01-30","Labor Kiel","Dr. Alt","Euthyroid on levothyroxine 75mcg. Continue same dose."),
        ("DEMO-DE-010","Free T4","15.2","pmol/L","12.0-22.0","normal","2026-01-30","Labor Kiel","Dr. Alt","Normal. Annual review in 12 months."),
        ("DEMO-TR-001","HbA1c","8.2","%","< 7.0%","high","2026-02-15","Acıbadem Lab","Dr. Kaya","Poorly controlled. Basal insulin initiation discussed — patient reluctant."),
        ("DEMO-TR-001","Fasting glucose","9.1","mmol/L","3.9-5.5","high","2026-02-15","Acıbadem Lab","Dr. Kaya","Significantly elevated."),
        ("DEMO-TR-001","Creatinine","1.4","mg/dL","0.7-1.2","high","2026-02-15","Acıbadem Lab","Dr. Özdemir","eGFR 52 — early nephropathy. ACE inhibitor continued."),
        ("DEMO-TR-001","Urine ACR","48","mg/g","< 30","high","2026-02-15","Acıbadem Lab","Dr. Özdemir","Microalbuminuria confirmed. Recheck in 3 months."),
        ("DEMO-TR-001","Total cholesterol","6.1","mmol/L","< 5.0","high","2026-02-15","Acıbadem Lab","Dr. Kaya","Dyslipidaemia — statin therapy initiated."),
        ("DEMO-TR-002","Anti-CCP antibody","180","IU/mL","< 17","high","2026-02-10","Ankara Lab","Dr. Acar","Strongly seropositive RA."),
        ("DEMO-TR-002","CRP","22","mg/L","< 5.0","high","2026-02-10","Ankara Lab","Dr. Acar","Active inflammation — DAS28 3.1. Consider MTX uptitration."),
        ("DEMO-TR-002","ALT","38","U/L","7-40","normal","2026-02-10","Ankara Lab","Dr. Acar","MTX hepatotoxicity monitoring — acceptable range."),
        ("DEMO-TR-002","Full Blood Count","WBC 5.2 / Hb 11.8 / PLT 188","mixed","Normal","borderline","2026-02-10","Ankara Lab","Dr. Acar","Mild anaemia of chronic disease. Monitor."),
        ("DEMO-TR-005","FEV1","58","% predicted","≥ 80%","low","2026-02-18","Solunum Lab Adana","Dr. Arslan","Declining from 62% last year. Smoking cessation critical."),
        ("DEMO-TR-005","SpO2 at rest","91","% on air","≥ 94%","low","2026-02-18","Solunum Lab Adana","Dr. Arslan","Borderline — ambulatory O2 assessment pending."),
        ("DEMO-TR-008","Haemoglobin","10.2","g/dL","12.0-16.0 (F)","low","2026-02-20","Antalya Lab","Dr. Koç","Improving on ferrous sulfate (was 9.8 at diagnosis)."),
        ("DEMO-TR-008","Ferritin","8","µg/L","12-150","low","2026-02-20","Antalya Lab","Dr. Koç","Depleted iron stores. Continue treatment for 3 more months."),
        ("DEMO-TR-008","MCV","72","fL","80-100","low","2026-02-20","Antalya Lab","Dr. Koç","Microcytic anaemia consistent with iron deficiency."),
        ("DEMO-TR-009","DAT (dopamine transporter scan)","Reduced uptake bilateral","qualitative","Normal bilateral uptake","abnormal","2021-03-10","Samsun Nükleer Tıp","Dr. Başar","Confirms nigrostriatal dopaminergic deficit. Consistent with PD."),
        ("DEMO-UK-001","NT-proBNP","1240","pg/mL","< 400","high","2026-02-12","NHS Lab London","Dr. Thompson","Elevated. Consistent with HFrEF. Monitor trend."),
        ("DEMO-UK-001","eGFR","55","ml/min/1.73m²","≥ 60","low","2026-02-12","NHS Lab London","Dr. Thompson","CKD stage 3a. Monitor on diuretic + ACEI."),
        ("DEMO-UK-001","Potassium","4.1","mmol/L","3.5-5.0","normal","2026-02-12","NHS Lab London","Dr. Thompson","Normal on furosemide + ramipril. Recheck in 3 months."),
        ("DEMO-UK-001","Sodium","138","mmol/L","133-146","normal","2026-02-12","NHS Lab London","Dr. Thompson","Normal. Fluid restriction maintained."),
        ("DEMO-UK-002","Peak Flow","480","L/min","400-550 (predicted)","normal","2026-01-20","NHS Lab London","Dr. Hall","Good. Continue current maintenance regimen."),
        ("DEMO-UK-002","FeNO","28","ppb","< 25 (low eosinophilic)","borderline","2026-01-20","NHS Lab London","Dr. Hall","Borderline eosinophilic inflammation. Monitor. Consider step-up if worsens."),
        ("DEMO-UK-003","HbA1c","7.2","%","< 7.5%","normal","2026-02-08","NHS Lab Edinburgh","Dr. MacDonald","Acceptable. Continue metformin."),
        ("DEMO-UK-003","eGFR","58","ml/min/1.73m²","≥ 60","borderline","2026-02-08","NHS Lab Edinburgh","Dr. MacDonald","Borderline CKD3a. Monitor metformin safety threshold."),
        ("DEMO-UK-004","Faecal calprotectin","85","µg/g","< 50","borderline","2026-01-28","NHS Lab Edinburgh","Dr. Reid","Borderline — may indicate subclinical inflammation. Endoscopy review at next colonoscopy."),
        ("DEMO-UK-004","Full Blood Count","WBC 7.1 / Hb 12.9 / PLT 320","mixed","Normal","normal","2026-01-28","NHS Lab Edinburgh","Dr. Reid","FBC monitoring on azathioprine — acceptable."),
        ("DEMO-UK-004","TPMT activity","Normal","qualitative","Normal activity","normal","2014-07-01","NHS Lab Edinburgh","Dr. Reid","Checked prior to azathioprine initiation — normal metaboliser."),
        ("DEMO-UK-006","HbA1c","7.1","%","< 7.5% (T1DM)","normal","2026-01-22","NHS Lab Birmingham","Dr. Sharma","Good control on insulin pump + CGM."),
        ("DEMO-UK-006","Thyroid antibodies","TPO ab negative","qualitative","Negative","normal","2026-01-22","NHS Lab Birmingham","Dr. Sharma","Annual screen for associated autoimmune conditions — normal."),
        ("DEMO-UK-007","Lithium level","0.78","mmol/L","0.6-0.8 (maintenance)","normal","2026-02-10","NHS Lab Bristol","Dr. Fletcher","Within therapeutic range. Continue 800mg BD."),
        ("DEMO-UK-007","TSH","1.8","mIU/L","0.4-4.0","normal","2026-02-10","NHS Lab Bristol","Dr. Fletcher","Annual thyroid screening on lithium — euthyroid."),
        ("DEMO-UK-007","eGFR","72","ml/min/1.73m²","≥ 60","normal","2026-02-10","NHS Lab Bristol","Dr. Fletcher","Annual renal monitoring on lithium — adequate function."),
        ("DEMO-UK-009","INR","2.4","ratio","2.0-3.0 (AF + aortic stenosis)","normal","2026-02-05","NHS Anticoag Clinic Leeds","Dr. Barker","In target range. Next check in 4 weeks."),
        ("DEMO-UK-009","Echocardiogram report","Mean gradient 28 mmHg, AVA 1.2 cm², EF 60%","qualitative","Reference per echo report","borderline","2026-01-15","Leeds Cardiac Imaging","Dr. Barker","Moderate AS — no significant interval change. Annual surveillance."),
        ("DEMO-UK-010","25-OH Vitamin D","32","nmol/L","50-150","low","2026-02-18","NHS Lab Liverpool","Dr. Osei","Deficient despite supplementation. Dose increase to 1000 IU daily."),
        ("DEMO-UK-010","dsDNA antibody","1:40","titre","< 1:10","high","2026-02-18","NHS Lab Liverpool","Dr. Osei","Mildly elevated. No new organ involvement. Continue HCQ. Monitor complement."),
        ("DEMO-UK-010","Complement C3","0.72","g/L","0.90-1.80","low","2026-02-18","NHS Lab Liverpool","Dr. Osei","Low complement — monitor for lupus flare. Repeat in 6 weeks."),
    ]
    con.executemany(
        "INSERT OR IGNORE INTO lab_results (health_number,test_name,value,unit,reference_range,status,test_date,lab_name,ordering_doctor,clinical_note) VALUES (?,?,?,?,?,?,?,?,?,?)",
        labs
    )

    # ------------------------------------------------------------------ ALLERGIES
    allergies = [
        ("DEMO-DE-001","Penicillin","Anaphylaxis — urticaria, angioedema, bronchospasm","severe","2005-06-10","Confirmed by immunologist. Avoid all penicillins. Use macrolide or clindamycin for alternatives. Cephalosporins with caution only."),
        ("DEMO-DE-001","Ibuprofen","GI bleed — haematemesis (hospitalised 2018)","moderate","2018-08-15","Avoid all NSAIDs. Use paracetamol for analgesia."),
        ("DEMO-DE-003","Aspirin","Severe bronchospasm — Samter's triad suspected","severe","2012-03-20","NSAID-exacerbated respiratory disease. Avoid all NSAIDs including COX-2 inhibitors."),
        ("DEMO-DE-006","Bee venom","Anaphylaxis — urticaria, stridor, hypotension. Required IM epinephrine.","severe","2019-06-01","Venom immunotherapy under evaluation. EpiPen x2 prescribed. MedicAlert bracelet worn."),
        ("DEMO-TR-001","Sulfonamides","Maculopapular rash","mild","2018-03-01","Avoid trimethoprim-sulfamethoxazole. Other antibiotics safe."),
        ("DEMO-TR-003","Codeine","Severe respiratory depression — ICU admission 2010","severe","2010-05-15","Avoid all opioids if possible. If required, use with extreme caution in monitored setting. Document prominently."),
        ("DEMO-UK-001","Aspirin","Severe bronchospasm","severe","2008-11-30","NSAID-exacerbated respiratory disease. Avoid all NSAIDs."),
        ("DEMO-UK-002","Latex","Urticaria and rhinitis on contact","moderate","2012-04-22","Alert surgical and procedural teams. Use latex-free equipment in all settings."),
        ("DEMO-UK-009","Digoxin","Toxicity at sub-therapeutic levels — bradycardia, visual halos","moderate","2020-01-05","Hypersensitivity to digoxin. Avoid in future management."),
        ("DEMO-UK-010","Sulfonamides","Photosensitive rash and SLE flare precipitated","moderate","2015-03-12","Avoid sulfa antibiotics. Document in SLE record. Use alternatives."),
    ]
    con.executemany(
        "INSERT OR IGNORE INTO allergies (health_number,allergen,reaction,severity,confirmed_date,notes) VALUES (?,?,?,?,?,?)",
        allergies
    )

    # ------------------------------------------------------------------ VISITS
    visits = [
        ("DEMO-DE-001","2025-11-12","Emergency","Klinikum Stuttgart","Cardiology",
         "Chest pain at rest, diaphoresis, radiation to left arm",
         "Unstable angina — ACS excluded by serial troponins x3 (peak 0.02 ng/mL)",
         "IV GTN infusion, aspirin 300mg loading, heparin IV, serial ECGs and troponins, monitoring",
         "Discharged after 12h observation. Statin uptitration recommended. Cardiology outpatient in 4 weeks.",
         "Dr. Schreiber",0,"2025-12-10"),
        ("DEMO-DE-002","2025-08-22","Emergency","LMU Klinikum München","Endocrinology",
         "Severe hypoglycaemia — BG 1.9 mmol/L, unresponsive, brought by paramedics",
         "Severe hypoglycaemia secondary to insulin pump over-infusion (basal rate error)",
         "IV dextrose 50% 50mL, pump suspended, BG monitored hourly — corrected to 6.0 mmol/L within 90 min",
         "Pump settings reviewed and corrected. Endocrinology follow-up 1 week. CGM low-glucose alarm reconfigured.",
         "Dr. Fischer",0,"2025-08-29"),
        ("DEMO-DE-003","2026-01-14","Emergency","UKE Hamburg","Respiratory",
         "Worsening dyspnoea over 4 days, purulent sputum, fever 38.2°C, SpO2 88% on air",
         "Infective exacerbation COPD — Haemophilus influenzae on sputum culture",
         "IV methylprednisolone 40mg OD, nebulised salbutamol + ipratropium QDS, doxycycline 100mg OD, controlled O2 via Venturi mask 28%",
         "Admitted 4 days. SpO2 improved to 94% by day 2. Discharged on 5-day oral prednisolone taper. Pulmonology follow-up 6 weeks.",
         "Dr. Hoffmann",4,"2026-02-25"),
        ("DEMO-TR-001","2025-12-05","Emergency","Acıbadem Maslak Hastanesi","Endocrinology",
         "Hyperglycaemia BG 22 mmol/L, vomiting x3, polyuria, polydipsia 3 days",
         "Mild DKA — pH 7.28, bicarbonate 14 mmol/L, ketones 3+ urine",
         "IV 0.9% NaCl 1L/h x2h, fixed-rate insulin infusion 0.1 unit/kg/h, potassium replacement, hourly BG monitoring",
         "Admitted 2 days. Ketosis resolved by 24h. Discharged with basal insulin glargine 10 units added. HbA1c 8.6% at admission.",
         "Dr. Özdemir",2,"2026-01-05"),
        ("DEMO-TR-003","2025-09-18","Emergency","Haseki EAH İstanbul","Cardiology",
         "Severe chest pain, diaphoresis, ST depression V3-V6, troponin rising",
         "NSTEMI — LAD territory (mid-LAD 80% stenosis on coronary angiogram)",
         "Emergency PCI — drug-eluting stent to mid-LAD. DAPT started: aspirin 100mg + ticagrelor 90mg BD.",
         "Uncomplicated. Day 4 discharge. Cardiac rehab enrolled. Secondary prevention medications reviewed.",
         "Dr. Çelik",4,"2025-10-20"),
        ("DEMO-UK-001","2025-10-08","Emergency","King's College Hospital","Cardiology",
         "Acute dyspnoea at rest, bilateral leg oedema to knees, orthopnoea, PND",
         "Decompensated heart failure — estimated 4L fluid overload. NT-proBNP 4200 on admission.",
         "IV furosemide 80mg BD, fluid restriction 1L/day, daily weight, strict I&O, telemetry monitoring",
         "Admitted 3 days. Weight reduced from 90 to 86kg (-4kg). Discharge with increased furosemide 80mg. HF clinic 2 weeks.",
         "Dr. Thompson",3,"2025-10-22"),
        ("DEMO-UK-002","2025-06-14","Emergency","Guy's Hospital","Emergency/Respiratory",
         "Status asthmaticus — unable to complete sentences, silent chest bilateral, SpO2 82% on air",
         "Life-threatening asthma exacerbation",
         "High-flow O2 15L, back-to-back nebulised salbutamol 5mg x3, IV magnesium sulfate 2g over 20 min, IV hydrocortisone 200mg. HDU admission.",
         "HDU day 1-3. Step-down to ward day 4. Discharged day 4 with prednisolone course. Asthma action plan reinforced. Respiratory f/u 2 weeks.",
         "Dr. Hall",3,"2025-06-28"),
        ("DEMO-TR-004","2023-04-22","Inpatient","Bursa City Hospital","Neurology",
         "Witnessed generalised tonic-clonic seizure at work, 90 seconds, post-ictal confusion",
         "Breakthrough seizure — sleep deprivation identified as trigger",
         "Observation 24h, levetiracetam dose reviewed (500mg BD continued), sleep hygiene counselled",
         "Discharged next day. MRI brain unchanged. Neurology f/u 4 weeks.",
         "Dr. Öztürk",1,"2023-05-20"),
        ("DEMO-UK-004","2024-11-10","Inpatient","Edinburgh Royal Infirmary","Gastroenterology",
         "Crohn's flare — bloody diarrhoea x8/day, CRP 68, faecal calprotectin 1800",
         "Moderate Crohn's flare — ileocolonic",
         "IV hydrocortisone 100mg QDS x3 days, then oral prednisolone 40mg tapering, azathioprine continued",
         "Response to IV steroids. Discharged on prednisolone taper. Biologics discussed for future management.",
         "Dr. Reid",5,"2024-12-01"),
        ("DEMO-UK-003","2025-03-05","Emergency","Edinburgh Royal Infirmary","Respiratory",
         "COPD exacerbation — worsening dyspnoea, green sputum, SpO2 85% on air",
         "Infective exacerbation COPD — Moraxella catarrhalis on sputum",
         "IV methylprednisolone, nebulised therapy, amoxicillin-clavulanate, controlled O2 24-28%",
         "Admitted 5 days. Discharged stable. Pulmonology review booked. Home nebuliser assessment.",
         "Dr. MacDonald",5,"2025-04-10"),
    ]
    con.executemany(
        "INSERT OR IGNORE INTO visits (health_number,visit_date,visit_type,hospital,department,chief_complaint,diagnosis,treatment,discharge_notes,attending_doctor,duration_days,follow_up_date) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        visits
    )

    # ------------------------------------------------------------------ SURGERIES
    surgeries = [
        ("DEMO-DE-001","2018-05-22","Percutaneous coronary intervention (PCI) — LAD stent",
         "Stable angina with significant LAD stenosis (70%) on stress imaging",
         "Dr. Schreiber","Dr. Koch","Klinikum Stuttgart",90,"Transradial approach",
         "Single-vessel disease. 70% mid-LAD stenosis. Successful DES implantation. TIMI 3 flow post-procedure.",
         "None","Successful revascularisation. Discharged next day.","DAPT for 12 months (aspirin lifelong). Annual cardiology follow-up."),
        ("DEMO-DE-005","2018-02-20","Pacemaker implantation — AAI (single-chamber atrial)",
         "Symptomatic sinus node dysfunction — bradycardia-tachycardia syndrome",
         "Dr. Richter","Dr. Müller","Uniklinik Köln",75,"Left subclavian venous access, infraclavicular pocket",
         "Normal coronary anatomy. Lead positioned in right atrial appendage. Threshold and sensing acceptable.",
         "Minimal — small haematoma resolved conservatively",
         "Pacing threshold excellent at implant. Rate response enabled.",
         "Device check at 6 weeks, 6 months, then annually. No driving for 1 week post-implant."),
        ("DEMO-TR-003","2015-01-22","Coronary artery bypass grafting (CABG) — triple vessel",
         "Triple vessel CAD — LAD, RCA, Cx all >70% stenosis",
         "Dr. Yavuz","Dr. Kızıltan","Florence Nightingale Hastanesi İstanbul",240,"Median sternotomy, cardiopulmonary bypass",
         "Triple vessel disease confirmed. LIMA to LAD, SVG to RCA, SVG to Cx. Good targets. EF 55% pre-op.",
         "Prolonged CPB time (110 min). Uncomplicated post-op course.",
         "Good graft flows. Extubated at 6h post-op. ICU 24h, ward 5 days.",
         "Discharge on aspirin, statin, beta-blocker, ACE inhibitor. Cardiac rehab enrolled. NSTEMI 2025 — stent to mid-LAD."),
        ("DEMO-TR-007","2020-03-15","Radical retropubic prostatectomy",
         "Prostate cancer Gleason 3+4=7, cT2b, PSA 8.6 ng/mL",
         "Dr. Yıldız","Dr. Sarıoğlu","Konya EAH",180,"Open retropubic approach",
         "Prostate 42g. Extracapsular extension not seen. Margins clear. 2/18 lymph nodes sampled — negative.",
         "None intraoperatively. Post-op urinary retention requiring catheter for 2 weeks.",
         "Pathology: pT2c N0 M0. Gleason 3+4=7. Clear margins. Biochemical remission.",
         "PSA undetectable at 3 months. Monitoring 6-monthly. Pelvic floor physiotherapy commenced."),
        ("DEMO-UK-002","2025-06-14","Emergency bronchoscopy — not performed (conservative management)",
         "Status asthmaticus — bronchoscopy considered but avoided after magnesium response",
         "Dr. Hall","—","Guy's Hospital",0,"N/A — bronchoscopy deferred",
         "Patient responded to magnesium sulfate and aggressive nebuliser therapy. No airway intervention required.",
         "None","Conservative management successful.",
         "Written asthma action plan updated. Self-management education reinforced."),
        ("DEMO-UK-004","2016-05-10","Diagnostic laparoscopy — Crohn's disease assessment",
         "Suspected Crohn's disease — recurrent RIF pain, positive faecal calprotectin, inconclusive colonoscopy",
         "Dr. Reid","Dr. Morrison","Edinburgh Royal Infirmary",60,"Laparoscopy — 3 ports",
         "Ileocaecal Crohn's confirmed. Thickened terminal ileum, fat-wrapping, no fistula. Biopsies taken.",
         "None","Histology confirmed transmural granulomatous inflammation. Crohn's diagnosed.",
         "Azathioprine initiated post-operatively. IBD nurse follow-up arranged."),
        ("DEMO-UK-008","2016-08-22","Diagnostic laparoscopy + diathermy — endometriosis",
         "Chronic pelvic pain, dysmenorrhoea, dyspareunia — endometriosis suspected",
         "Dr. Evans","Dr. Griffiths","University Hospital Wales",75,"Laparoscopy — 3 ports",
         "Stage II endometriosis — ovarian endometrioma right side 2cm, peritoneal deposits left uterosacral ligament. Diathermy performed.",
         "None","Stage II endometriosis confirmed and treated. Histology confirmed.",
         "OCP started for hormonal suppression. Gynaecology follow-up 6 months."),
    ]
    con.executemany(
        "INSERT OR IGNORE INTO surgeries (health_number,surgery_date,procedure_name,indication,surgeon,assistant_surgeon,hospital,duration_minutes,approach,findings,complications,outcome,postop_notes) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        surgeries
    )

    # ------------------------------------------------------------------ ANAESTHESIA
    anaesthesia = [
        ("DEMO-DE-001",None,"2018-05-22","Dr. Volker Heinz","Local anaesthesia with conscious sedation",
         "68y male. CAD, HTN, hyperlipidaemia. Penicillin allergy. Pre-op BP 145/88, HR 74. Fasting x6h.",
         "ASA II","Midazolam 2mg IV, fentanyl 50mcg IV, lignocaine 2% local (radial artery access site)",
         "Transradial access. No airway intervention required.",
         "Transient ST changes resolved post-stenting. BP stable throughout. No contrast reaction.",
         "Alert and comfortable at end of procedure. Discharged to ward. Radial haemostasis band applied."),
        ("DEMO-DE-005",None,"2018-02-20","Dr. Reinhardt","General anaesthesia",
         "80y male. Persistent AF, ex-smoker. Rivaroxaban withheld 24h pre-op. Echo EF 55%.",
         "ASA III","Propofol 150mg IV induction, sevoflurane maintenance, fentanyl 100mcg, rocuronium 30mg",
         "Endotracheal intubation — Grade I laryngoscopy. Extubated at end of procedure.",
         "Minor bradycardia on device testing — resolved spontaneously. Stable haemodynamics throughout.",
         "Extubated smoothly. Transferred to monitored bed. Haematoma noted at pocket — managed conservatively."),
        ("DEMO-TR-003",None,"2015-01-22","Dr. Çetinkaya","General anaesthesia — cardiac (CPB)",
         "64y male. Triple vessel CAD, LVEF 55%, HTN, ex-smoker 35 pack-years. Codeine allergy documented. Stopped aspirin 5 days pre-op.",
         "ASA IV","Fentanyl 10mcg/kg, midazolam 0.1mg/kg, pancuronium 0.1mg/kg, propofol infusion, sevoflurane",
         "Endotracheal intubation. Arterial line (radial), central line (right internal jugular), pulmonary artery catheter.",
         "CPB time 110 min, cross-clamp 85 min. Transfused 2 units pRBC. Vasopressors required post-CPB — noradrenaline 0.05mcg/kg/min, weaned within 2h.",
         "Extubated at 6h post-op. ICU 24h — haemodynamically stable. Good urine output throughout."),
        ("DEMO-TR-007",None,"2020-03-15","Dr. Şimşek","Spinal anaesthesia",
         "61y male. Prostate cancer. No significant cardiac or pulmonary history. BMI 27. Pre-op Hb 14.2.",
         "ASA II","Heavy bupivacaine 0.5% 3mL intrathecal at L3-4. Sedation with midazolam 1mg IV.",
         "Spinal block T8 level achieved. No airway intervention required.",
         "Mild hypotension at T+15 min — treated with IV ephedrine 6mg + 500mL crystalloid. Resolved promptly.",
         "Block regressed by 3h. Mobilised at 5h. No post-dural puncture headache."),
        ("DEMO-UK-004",None,"2016-05-10","Dr. Campbell","General anaesthesia",
         "23y female. No significant medical history. No allergies. BMI 21. Pre-op bloods normal.",
         "ASA I","Propofol 150mg IV, sevoflurane maintenance, fentanyl 75mcg, atracurium 25mg",
         "LMA Supreme size 3 — inserted smoothly. No airway difficulty.",
         "No intraoperative events. Laparoscopy well tolerated.",
         "Awake and alert in recovery. Mild nausea — ondansetron 4mg IV. Discharged same day."),
        ("DEMO-UK-008",None,"2016-08-22","Dr. Thomas","General anaesthesia",
         "32y female. No significant medical history. No allergies. BMI 22.5. Migraine history — avoid ergotamines.",
         "ASA I","Propofol 120mg IV, sevoflurane maintenance, fentanyl 50mcg, rocuronium 30mg",
         "Endotracheal intubation — Grade I laryngoscopy. No difficulty.",
         "No intraoperative events. Stable haemodynamics. Diathermy used safely.",
         "Smooth emergence. Paracetamol + ibuprofen for post-op analgesia. Discharged same day."),
    ]
    con.executemany(
        "INSERT OR IGNORE INTO anesthesia_records (health_number,surgery_id,anesthesia_date,anesthesiologist,anesthesia_type,preop_assessment,asa_class,agents_used,airway_management,intraop_events,recovery_notes) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        anaesthesia
    )

    # ------------------------------------------------------------------ IMAGING
    imaging = [
        ("DEMO-DE-001","2025-11-12","ECG","Chest",
         "Chest pain — ACS rule out",
         "Sinus rhythm 76 bpm. No ST elevation. Mild ST depression V4-V5 (1mm). T-wave flattening V4-V6. Old LBBB not present.",
         "Non-specific ST-T changes in lateral leads. No acute STEMI. Clinical correlation required.",
         "Dr. Schreiber","Dr. Schreiber","Klinikum Stuttgart"),
        ("DEMO-DE-001","2026-02-01","Coronary CT Angiography","Coronary arteries",
         "Surveillance post-PCI 2018",
         "LAD stent patent. No in-stent restenosis. Mild non-obstructive disease RCA and Cx. Left ventricular function preserved.",
         "Patent LAD stent. No haemodynamically significant new lesions.",
         "Dr. Braun (Radiology)","Dr. Becker","Labor Stuttgart Radiology"),
        ("DEMO-DE-002","2025-09-10","Abdominal Ultrasound","Abdomen",
         "Routine screening — T1DM, check for hepatomegaly/NAFLD",
         "Liver normal size, homogeneous echotexture. No fatty infiltration. Gallbladder normal. Kidneys normal bilaterally.",
         "No abnormality detected.",
         "Dr. Meier","Dr. Fischer","LMU Klinikum München"),
        ("DEMO-DE-003","2026-01-14","Chest X-Ray","Chest",
         "COPD exacerbation — pneumonia exclusion",
         "Hyperinflated lungs. Flat hemidiaphragms. No consolidation. No pneumothorax. Increased AP diameter. No pleural effusion.",
         "Findings consistent with COPD. No acute pneumonia or pneumothorax.",
         "Dr. Hartmann","Dr. Hoffmann","UKE Hamburg"),
        ("DEMO-DE-003","2026-01-14","HRCT Chest","Chest",
         "COPD staging and emphysema assessment",
         "Centrilobular emphysema predominantly upper lobes. Airway wall thickening. No fibrosis. No nodules. No bronchiectasis. Mild bullous change right apex.",
         "Moderate emphysema consistent with COPD GOLD II-III. No malignant features.",
         "Dr. Hartmann","Dr. Hoffmann","UKE Hamburg"),
        ("DEMO-DE-004","2021-03-15","MRI Brain","Brain",
         "Migraine with aura — exclude structural cause",
         "No intracranial mass, haemorrhage or infarction. Small non-specific white matter hyperintensities in periventricular regions (FLAIR). No cortical lesions.",
         "Non-specific white matter changes consistent with migraine. No structural pathology.",
         "Dr. Richter (Neuroradiology)","Dr. Braun","UKE Hamburg Neuroradiology"),
        ("DEMO-DE-005","2026-01-10","Echocardiogram","Heart",
         "AF — cardiac function assessment, pacemaker function check",
         "EF 55%. Mild LV hypertrophy. LA enlarged (4.6cm). Pacemaker lead in situ — tip position RAA. No valvular disease. No pericardial effusion.",
         "Preserved LV function. LA dilatation consistent with chronic AF. Pacemaker function satisfactory.",
         "Dr. Richter","Dr. Richter","Uniklinik Köln"),
        ("DEMO-DE-007","2026-02-15","Abdominal Ultrasound","Abdomen — liver",
         "Elevated ALT — NAFLD suspected",
         "Liver mildly enlarged (16cm). Increased echogenicity consistent with fatty infiltration (Grade I-II steatosis). No focal lesions. Portal vein normal.",
         "Mild hepatic steatosis — NAFLD. No focal liver lesion. Suggest metabolic workup and lifestyle intervention.",
         "Dr. Braun (Radiology)","Dr. König","Labor Hannover Radiology"),
        ("DEMO-DE-009","2026-02-08","Renal Ultrasound","Kidneys/urinary tract",
         "CKD monitoring — structural assessment",
         "Kidneys mildly reduced in size (right 9.8cm, left 9.5cm). Increased cortical echogenicity bilaterally. No hydronephrosis. No calculi. Bladder normal.",
         "Findings consistent with chronic kidney disease. No obstructive cause.",
         "Dr. Wolf (Radiology)","Dr. Wolf","Labor Nürnberg"),
        ("DEMO-TR-001","2026-02-15","Echocardiogram","Heart",
         "Hypertension — LV hypertrophy assessment",
         "Concentric LV hypertrophy. LVEDD 49mm, IVSd 13mm. EF 62%. Grade I diastolic dysfunction. No valvular pathology.",
         "LV hypertrophy consistent with hypertensive heart disease. Preserved systolic function.",
         "Dr. Özdemir","Dr. Kaya","Acıbadem Maslak Hastanesi"),
        ("DEMO-TR-001","2025-12-05","Chest X-Ray","Chest",
         "DKA admission — baseline",
         "Normal heart size. No pulmonary oedema. No consolidation. No pleural effusion.",
         "No acute cardiopulmonary pathology.",
         "Dr. Kaya (ED)","Dr. Özdemir","Acıbadem Maslak Hastanesi"),
        ("DEMO-TR-002","2026-02-10","Hand X-Ray","Hands bilateral",
         "RA — erosion surveillance",
         "Periarticular osteopenia bilateral MCP and PIP joints. Early marginal erosions at 2nd and 3rd MCP joints bilaterally. No subluxation.",
         "Early erosive change consistent with seropositive RA. No significant joint space narrowing. Compare with prior films.",
         "Dr. Acar (Radiology)","Dr. Acar","Ankara Özel Hastane"),
        ("DEMO-TR-003","2025-09-18","Coronary Angiography","Coronary arteries",
         "NSTEMI — troponin positive, ST depression V3-V6",
         "Patent CABG grafts to RCA and Cx. LIMA to LAD patent. New 80% stenosis mid-LAD native vessel. PCI performed.",
         "NSTEMI due to native LAD disease distal to LIMA anastomosis. Successful PCI with DES.",
         "Dr. Çelik","Dr. Çelik","Haseki EAH İstanbul"),
        ("DEMO-TR-004","2018-07-20","MRI Brain","Brain",
         "New-onset seizure — structural cause exclusion",
         "No cortical dysplasia, no tumour, no vascular malformation. Bilateral hippocampi symmetric and normal. No mesial temporal sclerosis.",
         "Normal MRI brain. Epilepsy — likely cryptogenic focal onset. EEG correlation required.",
         "Dr. Öztürk (Neuroradiology)","Dr. Öztürk","Bursa City Hospital"),
        ("DEMO-TR-005","2026-02-18","Chest X-Ray","Chest",
         "COPD monitoring",
         "Hyperinflated lungs. Flat diaphragms. Increased AP diameter. No consolidation. Mild bullous changes upper lobes bilaterally.",
         "Consistent with moderate-severe COPD. No acute infection.",
         "Dr. Arslan (Radiology)","Dr. Arslan","Solunum Lab Adana"),
        ("DEMO-TR-007","2019-03-05","MRI Pelvis","Prostate/pelvis",
         "Prostate cancer staging — pre-operative",
         "Prostate volume 42mL. Focal lesion right peripheral zone PI-RADS 4. No extracapsular extension. No seminal vesicle invasion. Pelvic LN not enlarged.",
         "PI-RADS 4 lesion — high suspicion for clinically significant prostate cancer. Staging: cT2b N0 M0.",
         "Dr. Yıldız (Radiology)","Dr. Yıldız","Konya EAH"),
        ("DEMO-TR-009","2021-03-10","DaTscan (dopamine transporter SPECT)","Brain — basal ganglia",
         "Parkinson disease diagnosis confirmation",
         "Markedly reduced dopamine transporter uptake bilateral putamina — left greater than right. Comma-shaped pattern lost. Consistent with nigrostriatal degeneration.",
         "Abnormal DaTscan — confirms nigrostriatal dopaminergic deficit consistent with Parkinson disease.",
         "Dr. Başar (Nuclear Medicine)","Dr. Başar","Samsun Nükleer Tıp"),
        ("DEMO-TR-010","2018-04-10","DEXA Scan","Lumbar spine and hip",
         "Post-menopausal woman — osteoporosis screening",
         "L1-L4 T-score -2.8, Z-score -1.2. Total hip T-score -2.4. Trabecular bone score low.",
         "Osteoporosis — T-score below -2.5 at lumbar spine. Bisphosphonate therapy indicated. FRAX 10-year hip fracture risk 8%.",
         "Dr. Erdoğan (Radiology)","Dr. Erdoğan","İstanbul Kemik Dansitometre Merkezi"),
        ("DEMO-UK-001","2026-02-12","Echocardiogram","Heart",
         "Heart failure — EF and haemodynamic assessment",
         "EF 40%. Dilated LV (LVEDD 62mm). Global hypokinesis. Moderate MR (functional). Raised E/e' ratio 16. No pericardial effusion.",
         "HFrEF. EF 40%. Functional MR. Diastolic dysfunction grade II. Consider device therapy if EF remains <35% at next review.",
         "Dr. Thompson","Dr. Thompson","King's College Hospital"),
        ("DEMO-UK-001","2025-10-08","Chest X-Ray","Chest",
         "Decompensated heart failure — admission",
         "Cardiomegaly. Bilateral perihilar haziness. Kerley B lines. Small bilateral pleural effusions. Upper lobe blood diversion.",
         "Pulmonary oedema consistent with decompensated heart failure.",
         "Dr. Thompson","Dr. Thompson","King's College Hospital"),
        ("DEMO-UK-002","2025-06-14","Chest X-Ray","Chest",
         "Status asthmaticus — pneumothorax/pneumonia exclusion",
         "Hyperinflated lungs. No pneumothorax. No consolidation. No pleural effusion.",
         "Findings consistent with severe asthma attack. No complications.",
         "Dr. Hall","Dr. Hall","Guy's Hospital"),
        ("DEMO-UK-004","2026-01-28","Colonoscopy Report","Colon and terminal ileum",
         "Annual Crohn's surveillance — azathioprine therapy",
         "Ileum: mild mucosal oedema, no active ulceration. Colon: normal mucosa throughout. Biopsies taken from terminal ileum — mild chronic inflammation only. No dysplasia.",
         "Crohn's in endoscopic remission. Continue azathioprine. Repeat colonoscopy in 12 months.",
         "Dr. Reid","Dr. Reid","Edinburgh Royal Infirmary"),
        ("DEMO-UK-007","2023-09-15","MRI Brain","Brain",
         "Lithium therapy — baseline neurological screening",
         "No cerebral atrophy beyond age-expected. No white matter lesions. No cerebellar changes. Normal findings.",
         "Normal MRI brain. No lithium-related structural changes identified.",
         "Dr. Fletcher (Neuroradiology)","Dr. Fletcher","Bristol Royal Infirmary"),
        ("DEMO-UK-008","2016-08-22","Pelvic Ultrasound","Pelvis",
         "Pre-operative assessment — endometriosis",
         "Uterus anteverted, normal size. Right ovary: 2.1cm endometrioma ('ground glass' appearance). Left ovary normal. No free fluid.",
         "Right ovarian endometrioma 2.1cm. Consistent with endometriosis. Proceed to diagnostic laparoscopy.",
         "Dr. Evans","Dr. Evans","University Hospital Wales"),
        ("DEMO-UK-009","2026-01-15","Echocardiogram","Heart — aortic valve",
         "Moderate aortic stenosis — annual surveillance",
         "Aortic valve: tricuspid, calcified, restricted opening. AVA 1.2 cm². Mean gradient 28 mmHg, peak 46 mmHg. EF 60%. LV not hypertrophied. Mild AR (trivial). AF rhythm noted.",
         "Moderate aortic stenosis — unchanged from 2025. EF preserved. Surveillance echo in 12 months. AVR discussion if progression to severe.",
         "Dr. Barker","Dr. Barker","Leeds General Infirmary"),
        ("DEMO-UK-010","2025-06-10","MRI Brain and Spine","Brain and cervical spine",
         "SLE — neuropsychiatric screening, headache evaluation",
         "No cortical infarcts. No white matter lesions beyond age-expected. No evidence of NPSLE. Cervical spine — mild C5/6 disc degeneration, no cord compression.",
         "No neurological manifestations of SLE identified on MRI. Reassuring.",
         "Dr. Osei (Neuroradiology)","Dr. Osei","Royal Liverpool Hospital"),
    ]
    con.executemany(
        "INSERT OR IGNORE INTO imaging (health_number,study_date,modality,body_region,indication,findings,impression,radiologist,ordering_doctor,facility) VALUES (?,?,?,?,?,?,?,?,?,?)",
        imaging
    )

    # ------------------------------------------------------------------ ECG RECORDS
    ecgs = [
        ("DEMO-DE-001","2025-11-12T09:15:00","Sinus rhythm",76,164,88,"420/435","Normal","1mm ST depression V4-V5. T-wave flattening V4-V6. No ST elevation. Normal axis.","Non-specific lateral ST-T changes. No STEMI. ACS workup continued.","Dr. Schreiber"),
        ("DEMO-DE-005","2026-01-10T10:00:00","Atrial fibrillation",68,None,88,"—/420","Left axis deviation","Irregularly irregular rhythm. No P waves. Rate 68 bpm (rate controlled). No ST changes. Pacemaker spikes visible — AAI mode.","AF with pacemaker sensing appropriately. Rate controlled. No ischaemic changes.","Dr. Richter"),
        ("DEMO-DE-007","2026-02-12T10:15:00","Sinus rhythm",84,162,88,"390/430","Normal","Normal sinus rhythm. No ST changes. Mild LV voltage criteria (Sokolow-Lyon 38mm). QTc normal.","Normal ECG. Mild voltage criteria for LVH. No ischaemia.","Dr. König"),
        ("DEMO-TR-001","2026-02-15T11:45:00","Sinus rhythm",86,168,90,"410/440","Left axis deviation","Sinus rhythm. LV hypertrophy by voltage criteria. Mild ST flattening V4-V6. No acute changes.","LVH on ECG consistent with hypertension. No acute ischaemia.","Dr. Kaya"),
        ("DEMO-TR-003","2025-09-18T08:30:00","Sinus rhythm",88,164,92,"380/410","Normal","ST depression 1.5-2mm V3-V6. T-wave inversion V3-V4. No STEMI. Troponin rising — NSTEMI confirmed.","NSTEMI pattern. Emergency catheterisation lab activated.","Dr. Çelik"),
        ("DEMO-UK-001","2026-02-12T10:05:00","Sinus rhythm with LBBB",68,None,142,"420/435","Left","Left bundle branch block (new vs old — comparison pending). Rate 68 bpm. Concordant ST changes only.","LBBB. Rate controlled. No acute STEMI equivalent pattern. Compare with prior ECGs.","Dr. Thompson"),
        ("DEMO-UK-009","2026-02-05T09:10:00","Atrial fibrillation",74,None,88,"—/430","Normal","Irregularly irregular. No P waves. Ventricular rate 74 bpm. No ST changes. No delta waves.","AF — chronic. Rate well controlled. No acute ischaemia.","Dr. Barker"),
        ("DEMO-UK-007","2026-02-10T14:35:00","Sinus rhythm",70,160,88,"400/420","Normal","Normal sinus rhythm. QTc 420ms — normal (lithium monitoring). No ST changes.","Normal ECG. QTc acceptable on lithium therapy.","Dr. Fletcher"),
    ]
    con.executemany(
        "INSERT OR IGNORE INTO ecg_records (health_number,recorded_at,rhythm,rate_bpm,pr_interval_ms,qrs_duration_ms,qt_qtc_ms,axis,findings,interpretation,ordering_doctor) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        ecgs
    )

    # ------------------------------------------------------------------ EMG RECORDS
    emg_records = [
        ("DEMO-TR-009","2021-02-15",
         "Right APB, FDI, ADM, biceps, triceps, tibialis anterior, gastrocnemius",
         "Median, ulnar, radial motor + sensory; common peroneal, tibial, sural",
         "Motor unit potentials of reduced amplitude in right upper limb — consistent with bradykinesia. No fibrillations. Reduced recruitment pattern right APB and FDI. Normal sensory nerve conduction velocities bilaterally. No evidence of peripheral neuropathy.",
         "EMG/NCS: No peripheral neuropathy or myopathy. Findings consistent with parkinsonian syndrome affecting motor unit firing pattern. Supports clinical Parkinson disease diagnosis.",
         "Dr. Uysal (Neurophysiologist)","Samsun Nöroloji Kliniği"),
        ("DEMO-DE-004","2022-01-20",
         "Frontalis, temporalis bilateral — surface EMG",
         "Supraorbital nerve, auriculotemporal nerve — sensory latencies",
         "Normal EMG of cranial muscles. No central sensitisation pattern identified on QST. Supraorbital nerve sensory latency normal bilaterally.",
         "No neurophysiological abnormality detected. Migraine diagnosis remains clinical. Central sensitisation not confirmed on this assessment.",
         "Dr. Fischer (Neurophysiologist)","Neurologie Hamburg"),
        ("DEMO-UK-003","2020-05-12",
         "APB, EDB, tibialis anterior bilateral; intercostals",
         "Median, ulnar motor + sensory; peroneal, tibial, sural bilateral",
         "Normal motor and sensory nerve conduction velocities. No denervation. No myopathic changes. Mild reduction in sural nerve amplitude bilaterally — likely age-related.",
         "No significant peripheral neuropathy. Mild sural amplitude reduction — monitor. COPD symptoms not neurologically mediated.",
         "Dr. Grant (Neurophysiologist)","Edinburgh Neurophysiology"),
    ]
    con.executemany(
        "INSERT OR IGNORE INTO emg_records (health_number,study_date,muscles_tested,nerves_tested,findings,impression,neurologist,facility) VALUES (?,?,?,?,?,?,?,?)",
        emg_records
    )

    # ------------------------------------------------------------------ DOCTOR NOTES (SOAP)
    doctor_notes = [
        ("DEMO-DE-001","2026-02-01","Outpatient follow-up","Dr. Becker","Cardiology",
         "Patient reports no chest pain at rest. Occasional exertional chest tightness on climbing 2 flights of stairs. Compliant with all medications. Mild myalgia from statin — CK checked last visit, normal.",
         "BP 148/92. HR 76 bpm regular. SpO2 97.8%. Weight 84kg. No peripheral oedema. Heart sounds normal, no murmur. Lungs clear. ECG: sinus rhythm, old minor lateral ST-T changes.",
         "CAD with suboptimal LDL (2.8 mmol/L, target <1.8). Blood pressure above target (target <130/80). Statin therapy ongoing. ACE inhibitor in use.",
         "1. Uptitrate atorvastatin to 80mg or switch to rosuvastatin 40mg — discussed with patient. 2. Increase ramipril to 10mg if renal function permits — recheck eGFR in 6 weeks. 3. Consider adding amlodipine if BP remains elevated. 4. Repeat lipid profile in 8 weeks. 5. Coronary CTA arranged for stent surveillance.",
         None),
        ("DEMO-DE-002","2026-01-20","Outpatient follow-up","Dr. Fischer","Endocrinology",
         "Patient reports good glycaemic awareness. No severe hypoglycaemia since pump adjustment in August 2025. Using CGM full-time. Occasional nocturnal lows (BG 3.4-3.8 mmol/L) — managed with juice. No DKA symptoms.",
         "BP 112/70. HR 82. Weight 61kg. HbA1c 7.2%. No lipohypertrophy at infusion sites. Foot exam: normal sensation, intact skin. Eyes: ophthalmology review 2025 — no retinopathy.",
         "T1DM well controlled. HbA1c 7.2% (target <7.5%). Pump settings appropriate. CGM data reviewed — TIR 72%.",
         "1. Continue current insulin pump programme. 2. Adjust overnight basal to reduce nocturnal lows — reviewed with pump nurse. 3. HbA1c in 3 months. 4. Annual review: renal function, eyes, feet — all up to date. 5. No changes to other medications.",
         None),
        ("DEMO-TR-001","2026-02-15","Outpatient follow-up","Dr. Kaya","Endocrinology",
         "Patient frustrated. Reports eating large carbohydrate meals, irregular medication. BG at home 12-18 mmol/L fasting. Nocturia x3/night. Denies symptoms of DKA. Refuses insulin.",
         "BP 158/98. HR 86. Weight 87kg. BMI 28.7. HbA1c 8.2%. Urine ACR 48 mg/g. Feet: reduced monofilament sensation left 1st and 5th MTP. Eyes: fundoscopy — mild background diabetic retinopathy.",
         "Poorly controlled T2DM. Hypertension above target. Microalbuminuria. Early peripheral neuropathy. Mild NPDR on fundoscopy. Metabolic syndrome.",
         "1. Strongly recommend basal insulin — patient counselled again, declined for now. 2. Add Rosuvastatin 10mg for dyslipidaemia (TC 6.1). 3. Uptitrate amlodipine to 10mg. 4. Refer to diabetes nurse educator. 5. Ophthalmology referral for NPDR monitoring. 6. Podiatry referral for neuropathy. 7. Review again in 6 weeks.",
         None),
        ("DEMO-UK-001","2026-02-12","Outpatient HF clinic","Dr. Thompson","Cardiology",
         "Patient reports improved dyspnoea since last hospitalisation. Walking 200m on flat before stopping. Compliant with daily weighing — weight stable 86kg. Taking furosemide 80mg consistently.",
         "BP 142/88. HR 68 bpm. SpO2 96.5%. Weight 86kg (down from 90kg at discharge Oct 2025). JVP elevated 4cm. Mild bilateral ankle oedema. Lungs — fine basal crackles right. Echo: EF 40%, functional MR.",
         "HFrEF — partially compensated. NYHA II-III. NT-proBNP 1240 (improved from 4200 at admission). Renal function borderline (eGFR 55).",
         "1. Continue furosemide 80mg — weigh daily, self-adjust +/- 20mg based on weight chart provided. 2. Maintain ramipril 10mg — renal function acceptable. 3. Consider adding eplerenone (MRA) — check potassium first. 4. HF nurse follow-up in 4 weeks. 5. CRT-D assessment if EF remains <35% at next echo. 6. Device clinic referral pending.",
         None),
        ("DEMO-UK-007","2026-02-10","Psychiatry outpatient","Dr. Fletcher","Psychiatry",
         "Patient reports stable mood for 4 months. Sleeping 7-8h/night. No hypomanic or depressive symptoms. Wife concurs — no mood fluctuations observed. Continuing lithium 800mg BD consistently.",
         "Euthymic, well-groomed. Coherent speech, normal rate. No thought disorder. No suicidal ideation. Lithium level 0.78 mmol/L (therapeutic). TSH 1.8 (normal). eGFR 72 (stable). Mild fine tremor both hands — longstanding.",
         "Bipolar disorder type I — stable remission on lithium. Good adherence. Lithium level and renal/thyroid function satisfactory.",
         "1. Continue lithium 800mg BD. 2. Lithium level + renal function in 3 months. 3. Annual thyroid and renal function monitoring maintained. 4. Reinforce sleep hygiene — regular schedule, avoid shifts. 5. Next psychiatry review in 3 months.",
         None),
        ("DEMO-TR-002","2026-02-10","Rheumatology outpatient","Dr. Acar","Rheumatology",
         "Moderate morning stiffness lasting 45 minutes. Bilateral MCP joint pain and swelling. Fatigue affecting work performance. MTX causing nausea day of and after dose — managing with ginger tea and folic acid.",
         "Tender and swollen MCPs bilaterally (2nd-4th). DAS28-CRP 3.1. Grip strength mildly reduced. No extra-articular features. CRP 22 mg/L. Anti-CCP 180 IU/mL.",
         "Seropositive RA — low-moderate disease activity (DAS28 3.1). Suboptimal response to current MTX 15mg/week. DMARD escalation warranted.",
         "1. Uptitrate MTX to 20mg/week. 2. Folic acid continued 6 days/week. 3. If inadequate response in 3 months — discuss biologic therapy (anti-TNF or JAK inhibitor). 4. Repeat CRP and DAS28 at next visit. 5. Annual ophthalmology review for HCQ (scheduled). 6. Physiotherapy referral for hand exercises.",
         None),
        # Mustafa Demir — DEMO-TR-003 (post-CABG, post-NSTEMI 2025)
        ("DEMO-TR-003","2026-01-25","Cardiology outpatient follow-up","Dr. Çelik","Cardiology",
         "Patient reports stable exertional tolerance. No chest pain, no rest symptoms. Compliant with DAPT (Ticagrelor + Aspirin). Reports mild breathlessness on climbing stairs — attributes to age. No syncope, no palpitations. Wife present at visit.",
         "BP 136/84 mmHg. HR 70 bpm regular sinus. SpO2 96%. Weight 78kg, BMI 27. No peripheral oedema. Heart sounds: normal S1/S2, no murmur. Lungs clear bilaterally. ECG: sinus rhythm, old anterior Q-waves (known), no new ST changes. LDL 1.6 mmol/L (at target).",
         "CAD post-CABG 2015 and post-NSTEMI with mid-LAD PCI (Sep 2025) — stable. DAPT ongoing and well tolerated. Blood pressure within target range. LDL at goal on rosuvastatin 20mg. Mild exertional dyspnoea — likely age-related deconditioning, no current evidence of ACS or HF decompensation.",
         "1. Continue Ticagrelor 90mg BD + Aspirin 100mg OD until Sep 2026 (12 months post-PCI). 2. Continue Bisoprolol 5mg OD and Rosuvastatin 20mg ON. 3. AVOID CODEINE and all opioids — severe respiratory depression on record (ICU 2010). 4. Repeat ECG + troponin if any new chest pain or breathlessness at rest. 5. Next scheduled review Apr 2026 — post-NSTEMI DAPT decision point.",
         None),
        ("DEMO-TR-003","2025-09-18","Emergency cardiology admission note","Dr. Çelik","Cardiology",
         "76-year-old male, known CAD post-CABG 2015, presented to Haseki EAH Emergency with 3-hour history of central chest tightness, diaphoresis, and radiation to left arm. Onset at rest. Wife called ambulance.",
         "BP 158/96 on arrival. HR 88 bpm. SpO2 94% on air. ECG: ST depression 1.5-2mm V3-V6, T-wave inversion V3-V4. No STEMI criteria. Troponin I: 0.8 ng/mL rising to 2.4 ng/mL at 3h. CXR: no acute pulmonary oedema. Echo: EF 50%, mild hypokinesis anterolateral wall.",
         "NSTEMI — LAD territory (mid-LAD 80% stenosis on emergency coronary angiogram). High-risk features: dynamic troponin, ECG changes, known CAD. GRACE score 148 — high risk. Immediate angiography performed — successful PCI with DES to mid-LAD.",
         "1. Loading doses: Ticagrelor 180mg + Aspirin 300mg pre-procedure. 2. Emergency PCI performed — DES to mid-LAD, TIMI 3 flow restored. 3. Post-PCI: Ticagrelor 90mg BD + Aspirin 100mg OD for 12 months (DAPT). 4. Continue Bisoprolol and Rosuvastatin. 5. PROMINENT ALLERGY FLAG: Codeine — severe respiratory depression, ICU 2010. No opioids without senior review. 6. Discharge in 3 days. Outpatient review in 4 weeks.",
         None),
    ]
    con.executemany(
        "INSERT OR IGNORE INTO doctor_notes (health_number,note_date,note_type,author,department,subjective,objective,assessment,plan,full_note) VALUES (?,?,?,?,?,?,?,?,?,?)",
        doctor_notes
    )

    # ------------------------------------------------------------------ APPOINTMENTS
    appointments = [
        ("DEMO-DE-001","2026-04-08","09:30","Cardiology","Dr. Becker","Klinikum Stuttgart","Statin uptitration review + lipid profile","scheduled","Fasting blood test required morning of appointment."),
        ("DEMO-DE-001","2026-06-15","10:00","Cardiology","Dr. Schreiber","Klinikum Stuttgart","Coronary CTA result review","scheduled",None),
        ("DEMO-DE-002","2026-04-20","08:00","Endocrinology","Dr. Fischer","LMU Klinikum München","HbA1c + pump settings review","scheduled","Download pump and CGM data before appointment."),
        ("DEMO-DE-002","2026-10-15","10:30","Ophthalmology","Dr. Weiss","LMU Klinikum München","Annual diabetic retinopathy screening","scheduled",None),
        ("DEMO-DE-003","2026-02-25","11:00","Pulmonology","Dr. Hoffmann","UKE Hamburg","Post-exacerbation review + spirometry","scheduled","Do not use bronchodilator inhaler 4h before spirometry."),
        ("DEMO-DE-004","2026-03-12","14:00","Neurology","Dr. Braun","Neurologie Hamburg","Migraine frequency review + topiramate dose discussion","scheduled",None),
        ("DEMO-DE-005","2026-05-20","09:00","Cardiology/Device Clinic","Dr. Richter","Uniklinik Köln","Annual pacemaker check","scheduled","Device programming — bring pacemaker card."),
        ("DEMO-DE-007","2026-03-15","10:00","Endocrinology","Dr. König","Hannover Medical","HbA1c + NAFLD ultrasound result review","scheduled","Fasting 8h required for bloods."),
        ("DEMO-DE-009","2026-04-01","09:00","Nephrology","Dr. Neumeier","Klinikum Nürnberg","CKD3b review — nephrology first appointment","scheduled","Full renal panel including urine ACR."),
        ("DEMO-DE-010","2027-01-30","10:15","GP","Dr. Alt","Hausarztpraxis Kiel","Annual thyroid function test and levothyroxine review","scheduled",None),
        ("DEMO-TR-001","2026-03-28","11:00","Endocrinology","Dr. Kaya","Acıbadem Maslak","DM + HTN review — 6 week follow-up","scheduled","HbA1c, U&E, urine ACR fasting bloods."),
        ("DEMO-TR-001","2026-04-10","10:00","Ophthalmology","Dr. Güneş","Acıbadem Maslak","Diabetic retinopathy monitoring — NPDR","scheduled",None),
        ("DEMO-TR-001","2026-04-20","09:30","Podiatry","Podiatry Team","Acıbadem Maslak","Peripheral neuropathy foot assessment","scheduled",None),
        ("DEMO-TR-002","2026-05-12","10:00","Rheumatology","Dr. Acar","Ankara Özel Hastane","DAS28 reassessment — MTX dose uptitration review","scheduled","CRP and full blood count."),
        ("DEMO-TR-003","2026-04-20","09:00","Cardiology","Dr. Çelik","Haseki EAH","Post-NSTEMI DAPT review — 7 months post-PCI","scheduled","ECG and troponin if symptomatic."),
        ("DEMO-TR-004","2026-06-15","14:00","Neurology","Dr. Öztürk","Bursa City Hospital","Annual epilepsy review — levetiracetam","scheduled","Driving restriction discussed at each visit."),
        ("DEMO-TR-005","2026-03-20","09:30","Respiratory","Dr. Arslan","Adana EAH","COPD review + smoking cessation counselling","scheduled","Spirometry on arrival. Varenicline prescription to be discussed."),
        ("DEMO-TR-007","2026-06-01","10:00","Urology/Oncology","Dr. Yıldız","Konya EAH","6-monthly PSA surveillance","scheduled","PSA blood test 3 days before appointment."),
        ("DEMO-TR-009","2026-04-10","10:30","Neurology","Dr. Başar","Samsun EAH","Parkinson 6-monthly review — motor assessment","scheduled","Physiotherapy report to be brought."),
        ("DEMO-TR-010","2026-08-18","10:30","Endocrinology/Rheumatology","Dr. Erdoğan","İstanbul Osteoporoz Kl.","Annual DEXA + bisphosphonate review","scheduled",None),
        ("DEMO-UK-001","2026-03-12","09:00","Heart Failure Clinic","Dr. Thompson","King's College Hospital","HF nurse + echo review","scheduled","Daily weight chart to be brought."),
        ("DEMO-UK-001","2026-05-20","10:00","Cardiology","Dr. Thompson","King's College Hospital","Device therapy assessment — CRT-D suitability","scheduled","Echo result review."),
        ("DEMO-UK-002","2026-03-14","14:30","Respiratory","Dr. Hall","Guy's Hospital","Post-status asthmaticus review + FeNO","scheduled","Asthma action plan to be reviewed."),
        ("DEMO-UK-003","2026-04-10","09:00","Respiratory","Dr. MacDonald","Edinburgh Royal Infirmary","COPD + T2DM annual review","scheduled","Spirometry + HbA1c."),
        ("DEMO-UK-004","2026-07-28","11:00","Gastroenterology","Dr. Reid","Edinburgh Royal Infirmary","Annual colonoscopy — Crohn's surveillance","scheduled","Bowel prep instructions to be sent."),
        ("DEMO-UK-005","2026-04-18","10:00","GP","Dr. Patel","Manchester GP Practice","BP + gout annual review","scheduled","Fasting lipids and urate."),
        ("DEMO-UK-006","2026-04-22","09:00","Endocrinology","Dr. Sharma","Birmingham Children's/Adult T1DM","HbA1c + pump download review","scheduled",None),
        ("DEMO-UK-007","2026-05-10","14:00","Psychiatry","Dr. Fletcher","Bristol Royal Infirmary","Bipolar — lithium level + 3-monthly review","scheduled","Lithium level + renal/TFTs morning of appointment."),
        ("DEMO-UK-009","2026-03-05","09:00","Anticoagulation Clinic","Anticoag Nurse","Leeds General Infirmary","INR check — warfarin dose review","scheduled","No dietary changes in preceding week."),
        ("DEMO-UK-009","2026-12-10","10:00","Cardiology","Dr. Barker","Leeds General Infirmary","Annual echocardiogram — aortic stenosis surveillance","scheduled",None),
        ("DEMO-UK-010","2026-05-25","11:00","Rheumatology","Dr. Osei","Royal Liverpool Hospital","SLE review — complement and dsDNA","scheduled","Blood tests 1 week before appointment."),
    ]
    con.executemany(
        "INSERT OR IGNORE INTO appointments (health_number,appointment_date,appointment_time,department,doctor,hospital,purpose,status,notes) VALUES (?,?,?,?,?,?,?,?,?)",
        appointments
    )

    # ------------------------------------------------------------------ CONSENTS
    consents = [
        ("DEMO-DE-001","2018-05-21","Procedure consent","Percutaneous coronary intervention (PCI) with stent implantation","Dr. Schreiber",1,"Nurse Braun","Patient verbally confirmed understanding of risks including: arterial injury, stroke, MI, contrast nephropathy, need for emergency CABG (<1%). Signed written consent."),
        ("DEMO-DE-005","2018-02-19","Procedure consent","Single-chamber pacemaker implantation (AAI)","Dr. Richter",1,"Nurse Schmidt","Risks discussed: infection, lead dislodgement, haematoma, pneumothorax, device malfunction. Patient signed written consent form."),
        ("DEMO-DE-002","2025-08-22","Emergency treatment consent","IV dextrose and insulin pump suspension","Dr. Fischer",1,None,"Patient unable to consent on arrival (unconscious). Emergency treatment given per clinical necessity. Wife notified and retrospectively consented. Patient verbally agreed with management plan on recovery."),
        ("DEMO-TR-003","2015-01-21","Surgical consent","Triple vessel CABG — open heart surgery","Dr. Yavuz",1,"Nurse Doğan","Risks discussed in detail: death (<2%), stroke (<2%), renal failure, bleeding, infection, prolonged ventilation, graft failure. Patient and wife signed consent. Patient also signed blood transfusion consent."),
        ("DEMO-TR-003","2025-09-17","Procedure consent","Emergency coronary angiography and PCI","Dr. Çelik",1,"Nurse Yılmaz","Emergency consent obtained. Risks: contrast allergy, stroke, emergency surgery. Verbal consent given by patient, wife present and concurring. Written consent signed in catheterisation lab."),
        ("DEMO-TR-007","2020-03-14","Surgical consent","Radical retropubic prostatectomy","Dr. Yıldız",1,"Nurse Kaya","Risks discussed: urinary incontinence (10-20%), erectile dysfunction (50-80%), anastomotic leak, rectal injury, DVT/PE. Patient signed written consent with surgeon. Alternatives (radiotherapy, active surveillance) discussed."),
        ("DEMO-UK-002","2025-06-14","Emergency treatment consent","IV magnesium, IV steroids, HDU admission for status asthmaticus","Dr. Hall",1,None,"Patient unable to consent on arrival (severe respiratory distress). Emergency treatment given. Verbal consent obtained once SpO2 improved. Written consent signed retrospectively for HDU admission."),
        ("DEMO-UK-004","2016-05-09","Surgical consent","Diagnostic laparoscopy — Crohn's disease assessment","Dr. Reid",1,"Nurse Morrison","Risks: anaesthetic risks, port site injury, bowel perforation, conversion to open. Patient signed written consent."),
        ("DEMO-UK-008","2016-08-21","Surgical consent","Diagnostic laparoscopy and diathermy for endometriosis","Dr. Evans",1,"Nurse Thomas","Risks discussed: bowel or bladder injury, conversion to open, incomplete excision, recurrence of endometriosis. Patient signed written consent."),
        ("DEMO-UK-009","2017-06-09","Long-term treatment consent","Anticoagulation therapy with warfarin for AF","Dr. Barker",1,"Nurse Jenkins","Risks and benefits of warfarin discussed: bleeding risk, INR monitoring requirements, dietary interactions. Patient signed consent. Anticoagulation booklet provided."),
    ]
    con.executemany(
        "INSERT OR IGNORE INTO consents (health_number,consent_date,consent_type,procedure,obtained_by,patient_signed,witness,notes) VALUES (?,?,?,?,?,?,?,?)",
        consents
    )

    # ------------------------------------------------------------------ CONSULTATIONS
    consultations = [
        ("DEMO-DE-001","2025-11-12","Dr. Schreiber (ED)","Dr. Lange (Cardiology)","Cardiology",
         "68y male, CAD with prior LAD stent. Chest pain at rest, ECG lateral ST-T changes, troponin 0.02 ng/mL x3 (non-rising).",
         "No haemodynamic compromise. ECG non-diagnostic ST-T changes. Troponin trend negative for NSTEMI. Clinically unstable angina cannot be excluded.",
         "1. ACS excluded by serial troponins. 2. Unstable angina — admit for monitoring. 3. Uptitrate LDL-lowering therapy. 4. Outpatient cardiology review in 4 weeks with stress testing or CTA. 5. No immediate PCI required.",
         "urgent"),
        ("DEMO-DE-003","2026-01-14","Dr. Hoffmann (Respiratory)","Dr. Brandt (Microbiology)","Microbiology",
         "COPD exacerbation. Purulent sputum. Requesting sensitivity guidance for empirical therapy.",
         "Previous sputum cultures: Haemophilus influenzae (sensitive to amoxicillin, doxycycline). Current culture pending.",
         "Empirical doxycycline 100mg BD appropriate based on prior sensitivities and local antibiogram. If cultures show resistance, adjust accordingly. No MRSA risk factors.",
         "routine"),
        ("DEMO-TR-001","2022-11-19","Dr. Kaya (Endocrinology)","Dr. Özdemir (Nephrology)","Nephrology",
         "T2DM patient. Urine ACR 48 mg/g (microalbuminuria). Creatinine 1.4 mg/dL. Requesting nephrology input for management.",
         "Microalbuminuria confirmed x2 samples. eGFR 52. No haematuria. BP 158/98. Consistent with diabetic nephropathy.",
         "1. Commence ACE inhibitor (ramipril 5mg) — titrate to maximum tolerated dose. 2. Strict BP target <130/80. 3. Repeat ACR in 3 months. 4. Avoid nephrotoxic agents (NSAIDs, IV contrast if avoidable). 5. Renal dietitian referral for protein intake guidance. 6. Follow up nephrology in 6 months.",
         "routine"),
        ("DEMO-TR-002","2026-02-10","Dr. Acar (Rheumatology)","Dr. Kaya (Ophthalmology)","Ophthalmology",
         "Patient on hydroxychloroquine 400mg for 14 years. Annual retinal toxicity screening required.",
         "Fundoscopy: normal macula bilaterally. No pigmentary changes. Visual field test normal. OCT: no bull's-eye maculopathy.",
         "No HCQ retinal toxicity detected. Continue annual surveillance. Note cumulative dose 14 years x 400mg — dose reduction to 5mg/kg/day (approximately 300mg) recommended per current guidelines for long-term use.",
         "routine"),
        ("DEMO-UK-001","2025-10-08","Dr. Thompson (Cardiology)","Dr. Williams (Renal)","Nephrology",
         "HFrEF patient on ramipril 10mg + furosemide 80mg. eGFR 55, creatinine 112 — checking renal tolerance of diuresis.",
         "eGFR 55 — CKD3a. Creatinine stable compared to outpatient baseline. Electrolytes normal. Cardiorenal syndrome type 1 not present.",
         "1. Continue ramipril — renal function acceptable. 2. Monitor electrolytes and creatinine every 48h during IV furosemide. 3. Avoid NSAIDs and nephrotoxins. 4. If creatinine rises >25% above baseline, hold or reduce diuretic. 5. Outpatient renal review if eGFR <45.",
         "urgent"),
        ("DEMO-UK-004","2024-11-10","Dr. Reid (Gastroenterology)","Dr. Morrison (Colorectal Surgery)","Colorectal Surgery",
         "Crohn's flare — moderate. CRP 68. Faecal calprotectin 1800. Requesting surgical opinion re: need for resection.",
         "Colitis predominant pattern. No perforation, no abscess, no obstruction on CT. Surgical intervention not indicated at this time.",
         "1. Medical management appropriate — IV steroids first line. 2. If no response to steroids in 72h, reassess for emergency surgery. 3. Discuss biologics with gastroenterology for steroid-sparing. 4. No surgical intervention currently required. 5. Review again if clinical deterioration.",
         "urgent"),
        ("DEMO-UK-009","2019-12-10","Dr. Barker (Cardiology)","Dr. Singh (Cardiac Surgery)","Cardiac Surgery",
         "87y male. Moderate aortic stenosis (AVA 1.2 cm², mean gradient 28 mmHg). AF on warfarin. Requesting surgical assessment for future AVR planning.",
         "Moderate AS — not yet severe by haemodynamics or symptoms. Preserved EF. NYHA I-II. Surgical risk assessed using EuroSCORE II — estimated mortality 4.2% (intermediate risk).",
         "1. Not suitable for AVR at this stage — moderate AS, not yet severe. 2. Annual echocardiography for surveillance. 3. When progression to severe AS (AVA <1.0 cm² or mean gradient >40 mmHg) or symptoms develop, reassess for TAVI vs SAVR — TAVI preferred given age and comorbidities. 4. Continue medical management of AF and secondary prevention.",
         "routine"),
        ("DEMO-UK-007","2023-09-15","Dr. Fletcher (Psychiatry)","Dr. Grant (Nephrology)","Nephrology",
         "Bipolar patient on lithium for 22 years. eGFR 72 — requesting nephrology input for long-term lithium-related renal monitoring.",
         "eGFR 72 — adequate. No proteinuria. Polyuria present (lithium-induced nephrogenic diabetes insipidus — mild). No structural renal abnormality on ultrasound.",
         "1. eGFR stable and acceptable for continued lithium. 2. Annual renal function monitoring essential. 3. Maintain lithium levels at lowest effective range (0.6-0.8 mmol/L). 4. If eGFR falls below 45, formal nephrology review with consideration of lithium discontinuation vs renal protection. 5. Ensure adequate hydration — minimise NSAID and ACEI co-prescription.",
         "routine"),
    ]
    con.executemany(
        "INSERT OR IGNORE INTO consultations (health_number,consult_date,requesting_doctor,consulting_doctor,specialty,reason,findings,recommendations,urgency) VALUES (?,?,?,?,?,?,?,?,?)",
        consultations
    )

    logger.info("Seeded 30 demo patients with full clinical records (v3).")


# ------------------------------------------------------------------ PUBLIC API

def get_patient(health_number: str) -> Optional[dict]:
    with _conn() as con:
        row = con.execute("SELECT * FROM patients WHERE health_number=?", (health_number,)).fetchone()
        return dict(row) if row else None


def get_full_record(health_number: str) -> Optional[dict]:
    p = get_patient(health_number)
    if not p:
        return None
    with _conn() as con:
        result = {
            "demographics": p,
            "patient":      p,
            "diagnoses":    [dict(r) for r in con.execute("SELECT * FROM diagnoses   WHERE health_number=? ORDER BY diagnosed_date DESC", (health_number,)).fetchall()],
            "medications":  [dict(r) for r in con.execute("SELECT * FROM medications WHERE health_number=? ORDER BY status, start_date DESC", (health_number,)).fetchall()],
            "lab_results":  [dict(r) for r in con.execute("SELECT * FROM lab_results WHERE health_number=? ORDER BY test_date DESC", (health_number,)).fetchall()],
            "vitals":       [dict(r) for r in con.execute("SELECT * FROM vitals      WHERE health_number=? ORDER BY recorded_at DESC LIMIT 10", (health_number,)).fetchall()],
            "visits":       [dict(r) for r in con.execute("SELECT * FROM visits      WHERE health_number=? ORDER BY visit_date DESC LIMIT 10", (health_number,)).fetchall()],
            "allergies":    [dict(r) for r in con.execute("SELECT * FROM allergies   WHERE health_number=?", (health_number,)).fetchall()],
            "surgeries":    [dict(r) for r in con.execute("SELECT * FROM surgeries   WHERE health_number=? ORDER BY surgery_date DESC", (health_number,)).fetchall()],
            "anesthesia":   [dict(r) for r in con.execute("SELECT * FROM anesthesia_records WHERE health_number=? ORDER BY anesthesia_date DESC", (health_number,)).fetchall()],
            "imaging":      [dict(r) for r in con.execute("SELECT * FROM imaging     WHERE health_number=? ORDER BY study_date DESC", (health_number,)).fetchall()],
            "ecg_records":  [dict(r) for r in con.execute("SELECT * FROM ecg_records WHERE health_number=? ORDER BY recorded_at DESC", (health_number,)).fetchall()],
            "emg_records":  [dict(r) for r in con.execute("SELECT * FROM emg_records WHERE health_number=? ORDER BY study_date DESC", (health_number,)).fetchall()],
            "doctor_notes": [dict(r) for r in con.execute("SELECT * FROM doctor_notes WHERE health_number=? ORDER BY note_date DESC", (health_number,)).fetchall()],
            "appointments": [dict(r) for r in con.execute("SELECT * FROM appointments WHERE health_number=? ORDER BY appointment_date ASC", (health_number,)).fetchall()],
            "consents":     [dict(r) for r in con.execute("SELECT * FROM consents    WHERE health_number=?", (health_number,)).fetchall()],
            "consultations":[dict(r) for r in con.execute("SELECT * FROM consultations WHERE health_number=? ORDER BY consult_date DESC", (health_number,)).fetchall()],
        }
        return result


def get_age(date_of_birth: str) -> int:
    try:
        return datetime.now().year - int(date_of_birth[:4])
    except Exception:
        return 0


def list_demo_health_numbers() -> list[str]:
    with _conn() as con:
        return [r[0] for r in con.execute(
            "SELECT health_number FROM patients ORDER BY nationality, health_number"
        ).fetchall()]


init_db()