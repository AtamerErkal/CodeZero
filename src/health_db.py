"""
Health Record Database — CodeZero v2
======================================
30 rich demo patients: 10 DE + 10 TR + 10 UK
Health number format: DEMO-DE-001, DEMO-TR-001, DEMO-UK-001
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

def init_db():
    with _conn() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS patients (
            health_number TEXT PRIMARY KEY, first_name TEXT NOT NULL, last_name TEXT NOT NULL,
            date_of_birth TEXT NOT NULL, sex TEXT NOT NULL, blood_type TEXT,
            nationality TEXT DEFAULT 'DE', language TEXT DEFAULT 'de-DE',
            email TEXT, phone TEXT, address TEXT, emergency_name TEXT, emergency_phone TEXT,
            insurance_id TEXT, gp_name TEXT, height_cm REAL, weight_kg REAL, notes TEXT);
        CREATE TABLE IF NOT EXISTS diagnoses (
            id INTEGER PRIMARY KEY AUTOINCREMENT, health_number TEXT NOT NULL,
            icd_code TEXT, description TEXT NOT NULL, status TEXT DEFAULT 'active',
            diagnosed_date TEXT, diagnosing_doctor TEXT, notes TEXT);
        CREATE TABLE IF NOT EXISTS medications (
            id INTEGER PRIMARY KEY AUTOINCREMENT, health_number TEXT NOT NULL,
            name TEXT NOT NULL, dosage TEXT, frequency TEXT, start_date TEXT, end_date TEXT,
            prescribing_doctor TEXT, status TEXT DEFAULT 'active');
        CREATE TABLE IF NOT EXISTS lab_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT, health_number TEXT NOT NULL,
            test_name TEXT NOT NULL, value TEXT, unit TEXT, reference_range TEXT,
            status TEXT DEFAULT 'normal', test_date TEXT, lab_name TEXT);
        CREATE TABLE IF NOT EXISTS vitals (
            id INTEGER PRIMARY KEY AUTOINCREMENT, health_number TEXT NOT NULL,
            recorded_at TEXT NOT NULL, bp_systolic INTEGER, bp_diastolic INTEGER,
            heart_rate INTEGER, spo2 REAL, temperature REAL, weight_kg REAL,
            height_cm REAL, bmi REAL, glucose REAL);
        CREATE TABLE IF NOT EXISTS visits (
            id INTEGER PRIMARY KEY AUTOINCREMENT, health_number TEXT NOT NULL,
            visit_date TEXT NOT NULL, visit_type TEXT, hospital TEXT, department TEXT,
            chief_complaint TEXT, diagnosis TEXT, treatment TEXT,
            discharge_notes TEXT, attending_doctor TEXT);
        CREATE TABLE IF NOT EXISTS allergies (
            id INTEGER PRIMARY KEY AUTOINCREMENT, health_number TEXT NOT NULL,
            allergen TEXT NOT NULL, reaction TEXT, severity TEXT DEFAULT 'moderate',
            confirmed_date TEXT);
        """)
        _seed(con)

def _seed(con):
    if con.execute("SELECT COUNT(*) FROM patients").fetchone()[0] > 0:
        return
    
    rows = [
        # DEMO-DE patients (10)
        ("DEMO-DE-001","Klaus","Müller","1958-04-12","Male","A+","DE","de-DE","k.mueller@email.de","+49 711 100 1001","Königstraße 12, 70173 Stuttgart","Greta Müller","+49 711 100 2001","AOK-BW 111222333","Dr. Hans Becker",178.0,84.0,"Known CAD, hypertension, hyperlipidaemia. Statins + ACE inhibitor."),
        ("DEMO-DE-002","Anna","Schneider","1985-07-23","Female","O+","DE","de-DE","a.schneider@email.de","+49 89 200 2002","Maximilianstraße 5, 80539 München","Thomas Schneider","+49 89 200 3002","TK 444555666","Dr. Maria Fischer",165.0,61.0,"Type 1 diabetes since age 12. Insulin pump user."),
        ("DEMO-DE-003","Heinrich","Weber","1971-11-05","Male","B+","DE","de-DE","h.weber@email.de","+49 30 300 3003","Unter den Linden 22, 10117 Berlin","Sabine Weber","+49 30 300 4003","Barmer 777888999","Dr. Ute Hoffmann",181.0,91.0,"COPD stage 2, ex-smoker 10 years."),
        ("DEMO-DE-004","Sophie","Fischer","1992-03-14","Female","AB+","DE","de-DE","s.fischer@email.de","+49 40 400 4004","Alsterchaussee 8, 20149 Hamburg","Markus Fischer","+49 40 400 5004","DAK 222333444","Dr. Peter Braun",168.0,58.0,"Migraines with aura. Topiramate prophylaxis."),
        ("DEMO-DE-005","Wolfgang","Bauer","1945-09-30","Male","O-","DE","de-DE","w.bauer@email.de","+49 221 500 5005","Domstraße 3, 50667 Köln","Ingrid Bauer","+49 221 500 6005","AOK 333444555","Dr. Klaus Richter",175.0,79.0,"Atrial fibrillation on anticoagulation. Pacemaker 2018."),
        ("DEMO-DE-006","Lena","Wagner","2000-01-18","Female","A-","DE","de-DE","l.wagner@email.de","+49 69 600 6006","Zeil 15, 60313 Frankfurt","Petra Wagner","+49 69 600 7006","IKK 555666777","Dr. Andrea Schäfer",170.0,55.0,"Anaphylaxis history to bee stings. EpiPen carrier."),
        ("DEMO-DE-007","Thomas","Becker","1963-06-22","Male","B-","DE","de-DE","t.becker@email.de","+49 511 700 7007","Leinstraße 9, 30159 Hannover","Claudia Becker","+49 511 700 8007","HEK 666777888","Dr. Bernd König",183.0,96.0,"T2DM, obesity BMI 32.5. Metformin + empagliflozin."),
        ("DEMO-DE-008","Mia","Schmitt","1998-12-03","Female","O+","DE","de-DE","m.schmitt@email.de","+49 341 800 8008","Augustusplatz 1, 04109 Leipzig","Jan Schmitt","+49 341 800 9008","BKK 888999000","Dr. Eva Lehmann",163.0,52.0,"Moderate persistent asthma. ICS + SABA."),
        ("DEMO-DE-009","Franz","Kraus","1952-08-17","Male","A+","DE","de-DE","f.kraus@email.de","+49 911 900 9009","Kaiserstraße 4, 90403 Nürnberg","Helga Kraus","+49 911 900 0009","VdAK 100200300","Dr. Dieter Wolf",177.0,88.0,"CKD stage 3, gout, hyperuricaemia."),
        ("DEMO-DE-010","Emma","Zimmermann","1975-05-09","Female","AB-","DE","de-DE","e.zimm@email.de","+49 431 010 0110","Holstenstraße 1, 24103 Kiel","Paul Zimmermann","+49 431 010 0220","Knappschaft 400500600","Dr. Renate Alt",162.0,67.0,"Hypothyroidism on levothyroxine."),
        # DEMO-TR patients (10)
        ("DEMO-TR-001","Ahmet","Yılmaz","1965-03-10","Male","B+","TR","tr-TR","a.yilmaz@email.com","+90 212 111 1001","Bağcılar Mah. No:5, 34200 İstanbul","Fatma Yılmaz","+90 532 111 2001","SGK-5512873690","Dr. Mehmet Kaya",174.0,87.0,"T2DM, hypertension, microalbuminuria. Metformin + amlodipine."),
        ("DEMO-TR-002","Fatma","Kaya","1978-11-25","Female","A+","TR","tr-TR","f.kaya@email.com","+90 312 222 2002","Atatürk Blv. No:22, 06100 Ankara","Ali Kaya","+90 533 222 3002","SGK-6623984701","Dr. Zeynep Acar",160.0,63.0,"Rheumatoid arthritis. MTX + hydroxychloroquine."),
        ("DEMO-TR-003","Mustafa","Demir","1950-07-04","Male","O+","TR","tr-TR","m.demir@email.com","+90 232 333 3003","Konak Mah. No:8, 35250 İzmir","Ayşe Demir","+90 534 333 4003","SGK-7734095812","Dr. Hasan Çelik",170.0,78.0,"Ischaemic heart disease post-CABG 2015. Aspirin + statin + beta-blocker."),
        ("DEMO-TR-004","Zeynep","Şahin","1990-02-14","Female","AB+","TR","tr-TR","z.sahin@email.com","+90 224 444 4004","Nilüfer Mah. No:3, 16110 Bursa","Can Şahin","+90 535 444 5004","SGK-8845206923","Dr. Seda Öztürk",164.0,57.0,"Epilepsy, seizure-free 3 years. Levetiracetam."),
        ("DEMO-TR-005","Mehmet","Çelik","1972-09-19","Male","A-","TR","tr-TR","m.celik@email.com","+90 322 555 5005","Seyhan Mah. No:11, 01250 Adana","Emine Çelik","+90 536 555 6005","SGK-9956317034","Dr. Kamil Arslan",180.0,95.0,"COPD, chronic smoker. Tiotropium inhaler."),
        ("DEMO-TR-006","Ayşe","Arslan","1985-06-30","Female","B-","TR","tr-TR","a.arslan@email.com","+90 462 666 6006","Ortahisar Mah. No:7, 61080 Trabzon","Kemal Arslan","+90 537 666 7006","SGK-1067428145","Dr. Necla Doğan",157.0,54.0,"Hashimoto thyroiditis. Levothyroxine 75mcg."),
        ("DEMO-TR-007","Ali","Doğan","1958-12-08","Male","O-","TR","tr-TR","a.dogan@email.com","+90 332 777 7007","Meram Mah. No:14, 42250 Konya","Hatice Doğan","+90 538 777 8007","SGK-2178539256","Dr. Bilal Yıldız",172.0,82.0,"Prostate cancer post-prostatectomy 2020. PSA monitoring."),
        ("DEMO-TR-008","Elif","Yıldız","2002-04-22","Female","A+","TR","tr-TR","e.yildiz@email.com","+90 242 888 8008","Muratpaşa Mah. No:6, 07160 Antalya","Hüseyin Yıldız","+90 539 888 9008","SGK-3289640367","Dr. Aylin Koç",166.0,50.0,"Iron-deficiency anaemia. Ferrous sulfate."),
        ("DEMO-TR-009","İbrahim","Koç","1944-01-15","Male","AB+","TR","tr-TR","i.koc@email.com","+90 362 999 9009","İlkadım Mah. No:19, 55090 Samsun","Nuriye Koç","+90 530 999 0009","SGK-4390751478","Dr. Ercan Başar",168.0,73.0,"Parkinson disease, mild stage. Levodopa/carbidopa."),
        ("DEMO-TR-010","Hatice","Öztürk","1968-08-07","Female","O+","TR","tr-TR","h.ozturk@email.com","+90 212 010 0110","Kadıköy Mah. No:2, 34710 İstanbul","Osman Öztürk","+90 531 010 0220","SGK-5401862589","Dr. Serkan Erdoğan",158.0,70.0,"Osteoporosis. Calcium, vitamin D, bisphosphonate."),
        # DEMO-UK patients (10)
        ("DEMO-UK-001","James","Wilson","1955-06-15","Male","O+","UK","en-GB","j.wilson@nhs.uk","+44 7700 100 001","14 Baker Street, London W1U 3BW","Margaret Wilson","+44 7700 200 001","NHS-111222333","Dr. Sarah Thompson",176.0,86.0,"Ischaemic heart disease, heart failure EF 40%. Furosemide + bisoprolol + ramipril."),
        ("DEMO-UK-002","Emily","Clarke","1988-11-05","Female","O-","UK","en-GB","e.clarke@nhs.uk","+44 7700 100 002","22 Oxford Street, London W1D 1AN","James Clarke","+44 7700 200 002","NHS-222333444","Dr. Peter Hall",168.0,62.0,"Moderate asthma. Seretide + Ventolin. History of status asthmaticus."),
        ("DEMO-UK-003","Robert","Johnson","1945-02-28","Male","A+","UK","en-GB","r.johnson@nhs.uk","+44 7700 100 003","45 Princes Street, Edinburgh EH2 2BJ","Dorothy Johnson","+44 7700 200 003","NHS-333444555","Dr. Fiona MacDonald",180.0,84.0,"COPD + hypertension + T2DM. Multiple inhalers, metformin, amlodipine."),
        ("DEMO-UK-004","Charlotte","Brown","1992-08-11","Female","B+","UK","en-GB","c.brown@nhs.uk","+44 7700 100 004","8 Royal Mile, Edinburgh EH1 2PB","David Brown","+44 7700 200 004","NHS-444555666","Dr. Gordon Reid",165.0,58.0,"Crohn's disease on azathioprine. Annual colonoscopy."),
        ("DEMO-UK-005","William","Taylor","1960-04-03","Male","AB+","UK","en-GB","w.taylor@nhs.uk","+44 7700 100 005","33 Deansgate, Manchester M3 4LF","Susan Taylor","+44 7700 200 005","NHS-555666777","Dr. Angela Patel",182.0,92.0,"Hypertension, gout. Losartan, allopurinol."),
        ("DEMO-UK-006","Olivia","Martin","2001-09-17","Female","A-","UK","en-GB","o.martin@nhs.uk","+44 7700 100 006","7 Church Street, Birmingham B3 2NP","Richard Martin","+44 7700 200 006","NHS-666777888","Dr. Kevin Sharma",162.0,54.0,"Type 1 diabetes. Insulin pump + CGM. HbA1c 7.1%."),
        ("DEMO-UK-007","George","White","1970-07-22","Male","B-","UK","en-GB","g.white@nhs.uk","+44 7700 100 007","19 Broad Street, Bristol BS1 2HP","Helen White","+44 7700 200 007","NHS-777888999","Dr. Louise Fletcher",175.0,79.0,"Bipolar disorder. Lithium 800mg. Regular lithium levels."),
        ("DEMO-UK-008","Isabella","Davies","1983-12-01","Female","O+","UK","en-GB","i.davies@nhs.uk","+44 7700 100 008","55 High Street, Cardiff CF10 1BB","Thomas Davies","+44 7700 200 008","NHS-888999000","Dr. Rachel Evans",170.0,65.0,"Migraine + endometriosis. Sumatriptan PRN."),
        ("DEMO-UK-009","Henry","Moore","1938-03-19","Male","A+","UK","en-GB","h.moore@nhs.uk","+44 7700 100 009","3 Castle Street, Leeds LS1 2HL","Mary Moore","+44 7700 200 009","NHS-999000111","Dr. John Barker",171.0,75.0,"Aortic stenosis (moderate), AF on warfarin. Annual echo."),
        ("DEMO-UK-010","Amelia","Garcia","1977-06-28","Female","AB-","UK","en-GB","a.garcia@nhs.uk","+44 7700 010 010","12 Victoria Road, Liverpool L6 3AB","Carlos Garcia","+44 7700 020 020","NHS-000111222","Dr. Natalie Osei",164.0,68.0,"SLE on hydroxychloroquine. Vitamin D deficiency."),
    ]
    con.executemany("INSERT OR IGNORE INTO patients VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    
    diags = [
        ("DEMO-DE-001","I25.10","Coronary artery disease","active","2018-05-20","Dr. Becker","Stable"),
        ("DEMO-DE-001","I10","Essential hypertension","active","2015-03-10","Dr. Becker","Target BP <130/80"),
        ("DEMO-DE-001","E78.5","Hyperlipidaemia","active","2015-03-10","Dr. Becker","Statin therapy"),
        ("DEMO-DE-002","E10.9","Type 1 diabetes mellitus","active","2002-09-05","Dr. Fischer","Insulin pump"),
        ("DEMO-DE-003","J44.1","COPD stage 2","active","2016-07-12","Dr. Hoffmann","Tiotropium + LABA"),
        ("DEMO-DE-004","G43.101","Migraine with aura","active","2019-04-22","Dr. Braun","Topiramate prophylaxis"),
        ("DEMO-DE-005","I48.91","Persistent atrial fibrillation","active","2017-08-14","Dr. Richter","Anticoagulated"),
        ("DEMO-DE-005","Z95.0","Cardiac pacemaker in situ","active","2018-02-20","Dr. Richter","AAI pacemaker"),
        ("DEMO-DE-006","T78.2","Anaphylaxis — bee sting","active","2019-06-01","Dr. Schäfer","EpiPen"),
        ("DEMO-DE-007","E11.9","Type 2 diabetes mellitus","active","2014-11-03","Dr. König","HbA1c 7.8%"),
        ("DEMO-DE-007","E66.01","Obesity","active","2014-11-03","Dr. König","BMI 32.5"),
        ("DEMO-DE-008","J45.30","Moderate persistent asthma","active","2011-03-08","Dr. Lehmann","ICS + SABA"),
        ("DEMO-DE-009","N18.3","Chronic kidney disease stage 3","active","2019-09-18","Dr. Wolf","eGFR 42"),
        ("DEMO-DE-009","M10.9","Gout","active","2020-04-05","Dr. Wolf","Allopurinol"),
        ("DEMO-DE-010","E03.9","Hypothyroidism","active","2013-06-15","Dr. Alt","Levothyroxine 75mcg"),
        ("DEMO-TR-001","E11.9","Type 2 diabetes mellitus","active","2014-04-12","Dr. Kaya","HbA1c 8.2%"),
        ("DEMO-TR-001","I10","Essential hypertension","active","2016-08-03","Dr. Kaya","Amlodipine 5mg"),
        ("DEMO-TR-001","N08","Diabetic nephropathy","active","2022-11-19","Dr. Özdemir","Microalbuminuria"),
        ("DEMO-TR-002","M05.80","Rheumatoid arthritis","active","2012-03-07","Dr. Acar","MTX 15mg/week"),
        ("DEMO-TR-003","I25.10","CAD post-CABG","active","2015-01-20","Dr. Çelik","Triple vessel"),
        ("DEMO-TR-004","G40.909","Epilepsy","active","2018-07-14","Dr. Öztürk","Seizure-free 3 years"),
        ("DEMO-TR-005","J44.1","COPD moderate","active","2017-05-09","Dr. Arslan","FEV1 58%"),
        ("DEMO-TR-006","E06.3","Hashimoto thyroiditis","active","2016-09-22","Dr. Doğan","TPO ab positive"),
        ("DEMO-TR-007","C61","Prostate cancer, post-op","active","2019-03-10","Dr. Yıldız","PSA <0.1"),
        ("DEMO-TR-008","D50.9","Iron-deficiency anaemia","active","2023-02-18","Dr. Koç","Hb 9.8 at dx"),
        ("DEMO-TR-009","G20","Parkinson disease","active","2020-11-05","Dr. Başar","Hoehn-Yahr 2"),
        ("DEMO-TR-010","M81.0","Postmenopausal osteoporosis","active","2018-04-12","Dr. Erdoğan","T-score -2.8"),
        ("DEMO-UK-001","I25.10","Ischaemic heart disease","active","2016-09-14","Dr. Thompson","Stable"),
        ("DEMO-UK-001","I50.9","Heart failure EF 40%","active","2020-03-22","Dr. Thompson","NYHA II"),
        ("DEMO-UK-002","J45.20","Moderate asthma","active","2005-03-22","Dr. Hall","Well-controlled"),
        ("DEMO-UK-003","J44.1","COPD GOLD II","active","2012-06-08","Dr. MacDonald",""),
        ("DEMO-UK-003","E11.9","Type 2 diabetes","active","2015-01-20","Dr. MacDonald","HbA1c 7.2%"),
        ("DEMO-UK-004","K50.90","Crohn's disease","active","2014-07-09","Dr. Reid","Remission on aza"),
        ("DEMO-UK-005","I10","Essential hypertension","active","2011-08-12","Dr. Patel","Controlled"),
        ("DEMO-UK-005","M10.9","Gout","active","2018-02-28","Dr. Patel","Allopurinol"),
        ("DEMO-UK-006","E10.9","Type 1 diabetes","active","2015-11-03","Dr. Sharma","Pump + CGM"),
        ("DEMO-UK-007","F31.9","Bipolar disorder","active","2001-05-18","Dr. Fletcher","Stable"),
        ("DEMO-UK-008","G43.909","Migraine","active","2010-09-30","Dr. Evans","Sumatriptan"),
        ("DEMO-UK-008","N80.9","Endometriosis","active","2016-03-14","Dr. Evans","OCP"),
        ("DEMO-UK-009","I35.0","Aortic stenosis moderate","active","2019-12-10","Dr. Barker","Annual echo"),
        ("DEMO-UK-009","I48.91","Atrial fibrillation","active","2017-06-05","Dr. Barker","Warfarin INR 2-3"),
        ("DEMO-UK-010","M32.9","SLE","active","2009-08-24","Dr. Osei","HCQ 400mg"),
        ("DEMO-UK-010","E55.9","Vitamin D deficiency","active","2022-01-10","Dr. Osei","Supplementing"),
    ]
    con.executemany("INSERT INTO diagnoses (health_number,icd_code,description,status,diagnosed_date,diagnosing_doctor,notes) VALUES (?,?,?,?,?,?,?)", diags)
    
    meds = [
        ("DEMO-DE-001","Atorvastatin 40mg","40mg","Once daily","2018-05-25",None,"Dr. Becker","active"),
        ("DEMO-DE-001","Ramipril 5mg","5mg","Once daily","2015-03-15",None,"Dr. Becker","active"),
        ("DEMO-DE-001","Aspirin 100mg","100mg","Once daily","2018-05-25",None,"Dr. Becker","active"),
        ("DEMO-DE-001","Bisoprolol 5mg","5mg","Once daily","2020-01-10",None,"Dr. Becker","active"),
        ("DEMO-DE-002","Insulin (pump — NovoRapid)","variable","Continuous","2015-09-01",None,"Dr. Fischer","active"),
        ("DEMO-DE-003","Tiotropium 18mcg","18mcg","Once daily inhaled","2016-07-20",None,"Dr. Hoffmann","active"),
        ("DEMO-DE-003","Salmeterol/Fluticasone 50/250","2 puffs","BD inhaled","2016-07-20",None,"Dr. Hoffmann","active"),
        ("DEMO-DE-004","Sumatriptan 50mg","50mg","PRN","2019-04-25",None,"Dr. Braun","active"),
        ("DEMO-DE-004","Topiramate 25mg","25mg","Once daily","2022-03-01",None,"Dr. Braun","active"),
        ("DEMO-DE-005","Rivaroxaban 20mg","20mg","Once daily","2017-08-20",None,"Dr. Richter","active"),
        ("DEMO-DE-006","Epinephrine EpiPen 0.3mg","0.3mg","IM anaphylaxis","2019-06-05",None,"Dr. Schäfer","active"),
        ("DEMO-DE-007","Metformin 1000mg","1000mg","BD with meals","2014-11-10",None,"Dr. König","active"),
        ("DEMO-DE-007","Empagliflozin 10mg","10mg","Once daily","2020-06-15",None,"Dr. König","active"),
        ("DEMO-DE-008","Budesonide/Formoterol 200/6","2 puffs","BD","2011-03-15",None,"Dr. Lehmann","active"),
        ("DEMO-DE-008","Salbutamol 100mcg","2 puffs","PRN","2011-03-15",None,"Dr. Lehmann","active"),
        ("DEMO-DE-009","Allopurinol 300mg","300mg","Once daily","2020-04-10",None,"Dr. Wolf","active"),
        ("DEMO-DE-009","Ramipril 2.5mg","2.5mg","Once daily","2019-09-25",None,"Dr. Wolf","active"),
        ("DEMO-DE-010","Levothyroxine 75mcg","75mcg","Once daily fasting","2013-06-20",None,"Dr. Alt","active"),
        ("DEMO-TR-001","Metformin 1000mg","1000mg","BD","2014-04-15",None,"Dr. Kaya","active"),
        ("DEMO-TR-001","Amlodipine 5mg","5mg","Once daily","2016-08-10",None,"Dr. Kaya","active"),
        ("DEMO-TR-001","Aspirin 100mg","100mg","Once daily","2017-01-05",None,"Dr. Kaya","active"),
        ("DEMO-TR-002","Methotrexate 15mg","15mg","Once weekly","2012-03-15",None,"Dr. Acar","active"),
        ("DEMO-TR-002","Hydroxychloroquine 400mg","400mg","Once daily","2012-03-15",None,"Dr. Acar","active"),
        ("DEMO-TR-003","Aspirin 100mg","100mg","Once daily","2015-01-25",None,"Dr. Çelik","active"),
        ("DEMO-TR-003","Bisoprolol 5mg","5mg","Once daily","2015-01-25",None,"Dr. Çelik","active"),
        ("DEMO-TR-003","Rosuvastatin 20mg","20mg","Once daily","2015-01-25",None,"Dr. Çelik","active"),
        ("DEMO-TR-004","Levetiracetam 500mg","500mg","BD","2018-07-20",None,"Dr. Öztürk","active"),
        ("DEMO-TR-005","Tiotropium 18mcg","18mcg","Once daily","2017-05-15",None,"Dr. Arslan","active"),
        ("DEMO-TR-006","Levothyroxine 75mcg","75mcg","Once daily","2016-09-28",None,"Dr. Doğan","active"),
        ("DEMO-TR-007","Tamsulosin 400mcg","400mcg","Once daily","2020-01-15",None,"Dr. Yıldız","active"),
        ("DEMO-TR-008","Ferrous sulfate 200mg","200mg","BD with food","2023-02-22",None,"Dr. Koç","active"),
        ("DEMO-TR-009","Co-careldopa 125mg","125mg","TID","2020-11-10",None,"Dr. Başar","active"),
        ("DEMO-TR-010","Alendronic acid 70mg","70mg","Once weekly","2018-04-18",None,"Dr. Erdoğan","active"),
        ("DEMO-TR-010","Calcium/Vit D 1200mg","1 tablet","BD","2018-04-18",None,"Dr. Erdoğan","active"),
        ("DEMO-UK-001","Furosemide 40mg","40mg","Once daily","2020-03-25",None,"Dr. Thompson","active"),
        ("DEMO-UK-001","Bisoprolol 5mg","5mg","Once daily","2020-03-25",None,"Dr. Thompson","active"),
        ("DEMO-UK-001","Ramipril 10mg","10mg","Once daily","2020-03-25",None,"Dr. Thompson","active"),
        ("DEMO-UK-001","Atorvastatin 80mg","80mg","Once daily","2016-09-20",None,"Dr. Thompson","active"),
        ("DEMO-UK-002","Salmeterol/Fluticasone 50/250","2 puffs","BD","2015-04-01",None,"Dr. Hall","active"),
        ("DEMO-UK-002","Salbutamol 100mcg","2 puffs","PRN","2005-03-25",None,"Dr. Hall","active"),
        ("DEMO-UK-003","Metformin 500mg","500mg","BD","2015-01-25",None,"Dr. MacDonald","active"),
        ("DEMO-UK-003","Amlodipine 5mg","5mg","Once daily","2013-04-20",None,"Dr. MacDonald","active"),
        ("DEMO-UK-003","Tiotropium 18mcg","18mcg","Once daily","2012-06-15",None,"Dr. MacDonald","active"),
        ("DEMO-UK-004","Azathioprine 100mg","100mg","Once daily","2014-07-15",None,"Dr. Reid","active"),
        ("DEMO-UK-005","Losartan 100mg","100mg","Once daily","2011-08-20",None,"Dr. Patel","active"),
        ("DEMO-UK-005","Allopurinol 300mg","300mg","Once daily","2018-03-05",None,"Dr. Patel","active"),
        ("DEMO-UK-006","Insulin NovoRapid (pump)","variable","Continuous","2019-05-01",None,"Dr. Sharma","active"),
        ("DEMO-UK-007","Lithium carbonate 400mg","400mg","BD","2001-06-01",None,"Dr. Fletcher","active"),
        ("DEMO-UK-008","Sumatriptan 100mg","100mg","PRN","2010-10-05",None,"Dr. Evans","active"),
        ("DEMO-UK-009","Warfarin","variable","INR guided","2017-06-10",None,"Dr. Barker","active"),
        ("DEMO-UK-009","Atorvastatin 40mg","40mg","Once daily","2019-12-15",None,"Dr. Barker","active"),
        ("DEMO-UK-010","Hydroxychloroquine 400mg","400mg","Once daily","2009-09-01",None,"Dr. Osei","active"),
    ]
    con.executemany("INSERT INTO medications (health_number,name,dosage,frequency,start_date,end_date,prescribing_doctor,status) VALUES (?,?,?,?,?,?,?,?)", meds)

    vitals = [
        ("DEMO-DE-001","2026-02-01T09:00:00",148,92,76,97.8,36.6,84.0,178.0,26.5,5.2),
        ("DEMO-DE-002","2026-01-20T08:00:00",112,70,82,99.0,36.4,61.0,165.0,22.4,6.8),
        ("DEMO-DE-003","2026-02-10T11:00:00",138,84,88,93.0,36.8,91.0,181.0,27.7,4.9),
        ("DEMO-DE-004","2026-01-28T14:00:00",118,74,68,99.0,36.5,58.0,168.0,20.5,4.8),
        ("DEMO-DE-005","2026-02-05T09:30:00",132,80,62,97.0,36.4,79.0,175.0,25.8,5.1),
        ("DEMO-DE-006","2026-01-15T15:00:00",110,68,65,99.0,36.3,55.0,170.0,19.0,4.7),
        ("DEMO-DE-007","2026-02-12T10:00:00",144,90,84,97.5,36.7,96.0,183.0,28.7,7.4),
        ("DEMO-DE-008","2026-01-22T09:15:00",116,72,70,97.5,36.4,52.0,163.0,19.6,4.8),
        ("DEMO-DE-009","2026-02-08T08:45:00",152,94,78,95.5,36.6,88.0,177.0,28.1,5.3),
        ("DEMO-DE-010","2026-01-30T10:15:00",120,76,72,98.5,36.5,67.0,162.0,25.5,4.9),
        ("DEMO-TR-001","2026-02-15T11:30:00",158,98,86,96.8,37.0,87.0,174.0,28.7,9.2),
        ("DEMO-TR-002","2026-02-10T10:00:00",124,78,74,98.0,36.6,63.0,160.0,24.6,5.0),
        ("DEMO-TR-003","2026-01-25T09:00:00",136,84,70,96.0,36.7,78.0,170.0,27.0,5.2),
        ("DEMO-TR-004","2026-02-03T14:00:00",112,70,66,99.0,36.4,57.0,164.0,21.2,4.7),
        ("DEMO-TR-005","2026-02-18T09:30:00",138,86,92,91.0,36.9,95.0,180.0,29.3,5.1),
        ("DEMO-TR-006","2026-01-20T11:00:00",108,66,68,98.5,36.4,54.0,157.0,21.9,4.8),
        ("DEMO-TR-007","2026-02-05T09:00:00",126,78,72,98.0,36.5,82.0,172.0,27.7,5.0),
        ("DEMO-TR-008","2026-02-20T10:00:00",100,62,96,98.5,36.3,50.0,166.0,18.1,4.5),
        ("DEMO-TR-009","2026-01-28T09:30:00",118,72,68,97.5,36.6,73.0,168.0,25.9,5.1),
        ("DEMO-TR-010","2026-02-10T10:30:00",130,80,76,97.5,36.5,70.0,158.0,28.1,5.0),
        ("DEMO-UK-001","2026-02-12T10:00:00",142,88,68,96.5,36.6,86.0,176.0,27.7,5.3),
        ("DEMO-UK-002","2026-01-20T14:30:00",118,74,68,98.8,36.4,62.0,168.0,22.0,4.8),
        ("DEMO-UK-003","2026-02-08T09:00:00",144,90,82,92.5,36.8,84.0,180.0,25.9,6.8),
        ("DEMO-UK-004","2026-01-28T11:00:00",110,68,72,99.0,36.5,58.0,165.0,21.3,4.9),
        ("DEMO-UK-005","2026-02-15T10:00:00",148,92,78,97.5,36.6,92.0,182.0,27.8,5.1),
        ("DEMO-UK-006","2026-01-22T09:00:00",110,68,76,99.0,36.4,54.0,162.0,20.6,6.2),
        ("DEMO-UK-007","2026-02-10T14:30:00",122,76,70,98.5,36.5,79.0,175.0,25.8,4.9),
        ("DEMO-UK-008","2026-01-30T10:00:00",116,72,66,98.8,36.4,65.0,170.0,22.5,4.8),
        ("DEMO-UK-009","2026-02-05T09:00:00",136,82,74,97.0,36.6,75.0,171.0,25.6,5.2),
        ("DEMO-UK-010","2026-02-18T11:00:00",124,78,72,98.2,36.5,68.0,164.0,25.3,4.9),
    ]
    con.executemany("INSERT INTO vitals (health_number,recorded_at,bp_systolic,bp_diastolic,heart_rate,spo2,temperature,weight_kg,height_cm,bmi,glucose) VALUES (?,?,?,?,?,?,?,?,?,?,?)", vitals)

    labs = [
        ("DEMO-DE-001","HbA1c","5.4%","%","< 5.7%","normal","2026-02-01","Labor Stuttgart"),
        ("DEMO-DE-001","LDL Cholesterol","2.8 mmol/L","mmol/L","< 1.8","high","2026-02-01","Labor Stuttgart"),
        ("DEMO-DE-001","Troponin I","0.02 ng/mL","ng/mL","< 0.04","normal","2026-02-01","Labor Stuttgart"),
        ("DEMO-DE-001","eGFR","74 ml/min","ml/min","≥ 60","normal","2026-02-01","Labor Stuttgart"),
        ("DEMO-DE-002","HbA1c","7.2%","%","< 7.5%","normal","2026-01-20","Labor München"),
        ("DEMO-DE-003","FEV1","62% predicted","%","≥ 80%","low","2026-02-10","Lungenfunktion HH"),
        ("DEMO-DE-007","HbA1c","7.8%","%","< 7.0%","high","2026-02-12","Labor Hannover"),
        ("DEMO-DE-009","eGFR","42 ml/min","ml/min","≥ 60","low","2026-02-08","Labor Nürnberg"),
        ("DEMO-DE-009","Uric acid","520 µmol/L","µmol/L","< 420","high","2026-02-08","Labor Nürnberg"),
        ("DEMO-DE-010","TSH","2.1 mIU/L","mIU/L","0.4-4.0","normal","2026-01-30","Labor Kiel"),
        ("DEMO-TR-001","HbA1c","8.2%","%","< 7.0%","high","2026-02-15","Acıbadem Lab"),
        ("DEMO-TR-001","Fasting glucose","9.1 mmol/L","mmol/L","3.9-5.5","high","2026-02-15","Acıbadem Lab"),
        ("DEMO-TR-001","Creatinine","1.4 mg/dL","mg/dL","0.7-1.2","high","2026-02-15","Acıbadem Lab"),
        ("DEMO-TR-005","FEV1","58% predicted","%","≥ 80%","low","2026-02-18","Solunum Lab Adana"),
        ("DEMO-UK-001","NT-proBNP","1240 pg/mL","pg/mL","< 400","high","2026-02-12","NHS Lab London"),
        ("DEMO-UK-001","eGFR","55 ml/min","ml/min","≥ 60","low","2026-02-12","NHS Lab London"),
        ("DEMO-UK-002","Peak Flow","480 L/min","L/min","400-550","normal","2026-01-20","NHS Lab London"),
        ("DEMO-UK-006","HbA1c","7.1%","%","< 7.5%","normal","2026-01-22","NHS Lab Birmingham"),
        ("DEMO-UK-007","Lithium level","0.78 mmol/L","mmol/L","0.6-0.8","normal","2026-02-10","NHS Lab Bristol"),
        ("DEMO-UK-009","INR","2.4","ratio","2.0-3.0","normal","2026-02-05","NHS Lab Leeds"),
    ]
    con.executemany("INSERT INTO lab_results (health_number,test_name,value,unit,reference_range,status,test_date,lab_name) VALUES (?,?,?,?,?,?,?,?)", labs)

    allergies = [
        ("DEMO-DE-001","Penicillin","Anaphylaxis","severe","2005-06-10"),
        ("DEMO-DE-001","Ibuprofen","GI bleed","moderate","2018-08-15"),
        ("DEMO-DE-003","Aspirin","Bronchospasm","severe","2012-03-20"),
        ("DEMO-DE-006","Bee venom","Anaphylaxis","severe","2019-06-01"),
        ("DEMO-TR-001","Sulfonamides","Rash","mild","2018-03-01"),
        ("DEMO-TR-003","Codeine","Respiratory depression","severe","2010-05-15"),
        ("DEMO-UK-001","Aspirin","Bronchospasm","severe","2008-11-30"),
        ("DEMO-UK-002","Latex","Urticaria","moderate","2012-04-22"),
        ("DEMO-UK-009","Digoxin","Toxicity at low levels","moderate","2020-01-05"),
    ]
    con.executemany("INSERT INTO allergies (health_number,allergen,reaction,severity,confirmed_date) VALUES (?,?,?,?,?)", allergies)

    visits = [
        ("DEMO-DE-001","2025-11-12","Emergency","Klinikum Stuttgart","Cardiology","Chest pain at rest","Unstable angina — ACS excluded","IV GTN, monitoring","12h obs, cardiology f/u","Dr. Schreiber"),
        ("DEMO-DE-002","2025-08-22","Emergency","LMU Klinikum München","Endocrinology","Severe hypoglycaemia BG 1.9","Severe hypoglycaemia","IV glucose","Pump settings adjusted","Dr. Fischer"),
        ("DEMO-DE-003","2026-01-14","Emergency","Universitätsklinikum Hamburg-Eppendorf (UKE)","Respiratory","Acute COPD exacerbation","Infective exacerbation","IV steroids + nebulisers","Admitted 4 days","Dr. Hoffmann"),
        ("DEMO-TR-001","2025-12-05","Emergency","Acıbadem Maslak Hastanesi","Emergency","Hyperglycaemia BG 22 mmol/L","Mild DKA","IV insulin, fluids","Admitted 2 days","Dr. Özdemir"),
        ("DEMO-TR-003","2025-09-18","Emergency","Haseki EAH","Cardiology","Chest pain, diaphoresis","NSTEMI","PCI — coronary stent","Recovered well","Dr. Çelik"),
        ("DEMO-UK-001","2025-10-08","Emergency","King's College Hospital","Cardiology","SOB, leg oedema","Decompensated heart failure","IV furosemide","Admitted 3 days, -4kg","Dr. Thompson"),
        ("DEMO-UK-002","2025-06-14","Emergency","Guy's Hospital","Emergency","Status asthmaticus","Severe asthma","Magnesium IV, HDU","Day 3 discharge","Dr. Hall"),
    ]
    con.executemany("INSERT INTO visits (health_number,visit_date,visit_type,hospital,department,chief_complaint,diagnosis,treatment,discharge_notes,attending_doctor) VALUES (?,?,?,?,?,?,?,?,?,?)", visits)
    
    logger.info("Seeded 30 demo patients (10 DE + 10 TR + 10 UK)")

def get_patient(health_number: str) -> Optional[dict]:
    with _conn() as con:
        row = con.execute("SELECT * FROM patients WHERE health_number=?", (health_number,)).fetchone()
        return dict(row) if row else None

def get_full_record(health_number: str) -> Optional[dict]:
    p = get_patient(health_number)
    if not p:
        return None
    with _conn() as con:
        return {
            "patient":     p,
            "diagnoses":   [dict(r) for r in con.execute("SELECT * FROM diagnoses WHERE health_number=? ORDER BY diagnosed_date DESC", (health_number,)).fetchall()],
            "medications": [dict(r) for r in con.execute("SELECT * FROM medications WHERE health_number=? ORDER BY status,start_date DESC", (health_number,)).fetchall()],
            "lab_results": [dict(r) for r in con.execute("SELECT * FROM lab_results WHERE health_number=? ORDER BY test_date DESC", (health_number,)).fetchall()],
            "vitals":      [dict(r) for r in con.execute("SELECT * FROM vitals WHERE health_number=? ORDER BY recorded_at DESC LIMIT 10", (health_number,)).fetchall()],
            "visits":      [dict(r) for r in con.execute("SELECT * FROM visits WHERE health_number=? ORDER BY visit_date DESC LIMIT 10", (health_number,)).fetchall()],
            "allergies":   [dict(r) for r in con.execute("SELECT * FROM allergies WHERE health_number=?", (health_number,)).fetchall()],
        }

def get_age(date_of_birth: str) -> int:
    try: return datetime.now().year - int(date_of_birth[:4])
    except: return 0

def list_demo_health_numbers() -> list[str]:
    with _conn() as con:
        return [r[0] for r in con.execute("SELECT health_number FROM patients ORDER BY nationality, health_number").fetchall()]

init_db()