<div align="center">

<img src="docs/images/banner.png" alt="CodeZero Banner" width="100%"/>

<br/>

# ⚡ CodeZero

### Intelligent Pre-Hospital Emergency Triage System

**AI-powered triage that bridges the gap between first symptoms and hospital treatment — in any language, on any device.**

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Azure AI](https://img.shields.io/badge/Azure_AI-0078D4?style=for-the-badge&logo=microsoftazure&logoColor=white)](https://azure.microsoft.com/en-us/products/ai-services)
[![GPT-4+](https://img.shields.io/badge/GPT--4+-412991?style=for-the-badge&logo=openai&logoColor=white)](https://openai.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-22c55e?style=for-the-badge)](LICENSE)

[🚀 Quick Start](#-quick-start) · [🎯 How It Works](#-how-it-works) · [✨ Features](#-key-features) · [🏗️ Architecture](#%EF%B8%8F-architecture) · [🔌 API Reference](#-api-reference) · [🎬 Demo Scenarios](#-demo-scenarios)

---

</div>

> [!CAUTION]
> **Medical Disclaimer** — This is an educational and demonstration system. It is **NOT** a certified medical device and must **NOT** be used for real clinical triage decisions. Always call emergency services (**112** / **911**) in a genuine medical emergency.

<br/>

## 🧠 What is CodeZero?

**CodeZero** is a full-stack, AI-powered pre-hospital triage platform with two complementary interfaces:

- **VitalNavAI** — a mobile-first patient app where anyone can describe their emergency, answer AI-guided clinical questions, and be routed to the best available hospital.
- **ER Command Center** — a real-time hospital dashboard where ER staff see incoming patients, their AI-assessed triage level, live GPS location, estimated arrival time, and full medical history — *before* the patient arrives.

Unlike symptom checkers that end with a generic recommendation, CodeZero creates a **live two-sided connection**: the patient gets routed to the right hospital, and the ER gets the right preparation time.

<br/>

## ✨ Key Features

<table>
<tr>
<td width="50%">

### 🎙️ Voice-First, Any Language
Speak in your native language — Azure Speech auto-detects from **10 supported languages** with full RTL support (Arabic, Hebrew, Farsi). A waveform animation gives real-time feedback during recording. Text fallback always available.

### 🧬 Condition-Specific AI Questions
GPT-4 generates **clinically relevant, diagnosis-deepening follow-up questions** grounded in real medical guidelines via RAG. Questions are specific to the patient's exact complaint — chest pain gets STEMI rule-out questions, leg swelling gets DVT risk questions. **13+ condition-specific clinical protocols** cover the most common ER presentations.

### 📊 5-Step Guided Journey
A visual progress bar guides patients through: Language → Welcome → Complaint Input → Photo Upload → AI Questions → Consent → Triage Result. Every step is accessible via keyboard and touch.

</td>
<td width="50%">

### 🗺️ Real-Time GPS Tracking
The patient's live position streams continuously to the hospital dashboard via `watchPosition`. The ER map shows each incoming patient's exact location and trajectory, updated every 4 seconds. A built-in simulation mode demonstrates the feature without real GPS.

### 🏥 Live ER Command Center
Multi-panel dashboard with sortable patient cards (by Triage Level, ETA, Risk Score, Newest), KPI strip, full-screen Leaflet map, statistics charts, and PDF-ready reports. Emergency patient arrivals trigger a prominent full-width alert banner with animation.

### 🔒 GDPR-Compliant by Design
GPS coordinates rounded to ~1 km grid before storage. No names stored. Patient IDs are random ER codes. Privacy is engineered into every data layer — not bolted on afterward.

</td>
</tr>
</table>

<br/>

## 🎯 How It Works

```
  ╭──────────────────────────────────────────────────────────────────────╮
  │                      THE PATIENT JOURNEY                             │
  ╰──────────────────────────────────────────────────────────────────────╯

  ┌──────────┐    ┌───────────┐    ┌───────────────┐    ┌──────────────┐
  │ 🗣️ SPEAK  │───▶│ 🌍 DETECT  │───▶│ 🤖 ASSESS     │───▶│ 🏥 ROUTE     │
  │  or TYPE  │    │ LANGUAGE  │    │ & QUESTION   │    │ TO HOSPITAL  │
  └──────────┘    └───────────┘    └───────────────┘    └──────────────┘
       │                │                  │                    │
       ▼                ▼                  ▼                    ▼
  "My leg is       Auto-detected:    5 targeted Qs       Top 3 hospitals
   swollen and     🇩🇪 German         specific to         ranked by
   red since       → continues       DVT/thrombosis:     Effective ETA
   I flew back"    in Deutsch        • Swelling/warmth?  (travel time +
                                     • Recent travel?    occupancy load)
                                     • Injury or not?
                                     • Previous DVT?
                                     • Pain level?
                                          │
                                          ▼
                                   ┌─────────────┐
                                   │  TRIAGE      │
                                   │  EMERGENCY   │──▶ 🚨 ER NOTIFIED
                                   │  URGENT      │    Live GPS map
                                   │  ROUTINE     │    ETA countdown
                                   └─────────────┘    Medical history
```

**On the hospital side:**

```
  ╭──────────────────────────────────────────────────────────────────────╮
  │                   ER COMMAND CENTER — LIVE FEED                      │
  ╰──────────────────────────────────────────────────────────────────────╯

  ┌─────────────────────────────────────────────────────────────────────┐
  │  📊 KPI Strip     Total | 🚨 Emergencies | ⚠️ Urgent | ✅ Routine    │
  │  🔔 Alert Banner  EMERGENCY arriving in 4 min — Suspected DVT        │
  ├────────────────────────┬────────────────────────────────────────────┤
  │  📋 Patient Cards      │  🗺️ Live Leaflet Map                        │
  │                        │                                            │
  │  Sort: Triage│ETA│Risk │  Patient pins with triage colour coding     │
  │  Filter: All | Status  │  Real-time GPS tracks (updates every 4s)   │
  │                        │  Route lines to hospital                   │
  │  ┌───────────────────┐ │                                            │
  │  │ 🚨 VN-2026-4821   │ │                                            │
  │  │ Chest Pain · 22F  │ ├────────────────────────────────────────────┤
  │  │ ETA: 6 min        │ │  📈 Statistics Panel                       │
  │  │ Risk: 9/10        │ │  📄 Reports Tab                            │
  │  └───────────────────┘ │                                            │
  └────────────────────────┴────────────────────────────────────────────┘
```

<br/>

## 🏗️ Architecture

<div align="center">
<img src="docs/images/architecture.png" alt="CodeZero System Architecture" width="85%"/>
</div>

<br/>

```
┌──────────────────────────────────────────────────────────────────────────┐
│                 PATIENT  ←──  Mobile / Desktop Browser                   │
│                                                                          │
│   ui/patient_app_v12.html  ────────────────────▶  FastAPI Server         │
│   (VitalNavAI — standalone HTML, zero build step)   hospital_server.py   │
│                                                      :8001               │
│                                                           │              │
│   ┌───────────────────────────────────────────────────────┴────────┐    │
│   │                     Azure AI Services                          │    │
│   │                                                                │    │
│   │  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐   │    │
│   │  │ Azure Speech │  │ Azure OpenAI │  │  Azure AI Search   │   │    │
│   │  │ STT + Auto   │  │ GPT-4 / 5   │  │  Medical Knowledge │   │    │
│   │  │ Lang Detect  │  │ + RAG Triage │  │  Semantic Ranking  │   │    │
│   │  └──────────────┘  └──────────────┘  └────────────────────┘   │    │
│   │                                                                │    │
│   │  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐   │    │
│   │  │ Azure Trans- │  │  Azure Maps  │  │  Azure Content     │   │    │
│   │  │ lator 100+   │  │  ETA + Route │  │  Safety (optional) │   │    │
│   │  │ Languages    │  │  Live Traffic│  │  Input Filtering   │   │    │
│   │  └──────────────┘  └──────────────┘  └────────────────────┘   │    │
│   └────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│   SQLite Patient Queue  ←──  hospital_queue.py (GDPR-compliant)          │
│   Health Records DB     ←──  health_db.py (30 demo patients)            │
│                                    │                                     │
│   ui/hospital_dashboard_v9.html  ◀─┘  ER Staff Command Center           │
│   (standalone HTML — Leaflet map, sort, filter, live GPS)               │
└──────────────────────────────────────────────────────────────────────────┘
```

<br/>

## ☁️ Azure Services

| Service | Role in CodeZero | AI-102 Domain | Fallback |
|:---|:---|:---:|:---|
| **Azure OpenAI** (GPT-4/5) | Condition-specific question generation, triage assessment, clinical report | Generative AI | Rule-based engine + 13 clinical mock sets |
| **Azure AI Search** | Medical knowledge base — semantic RAG retrieval | Knowledge Mining | Local file keyword matching |
| **Azure AI Document Intelligence** | Extract clinical text from PDF guidelines | Knowledge Mining | Manual text files |
| **Azure Speech Services** | Voice input with automatic language detection | NLP | Browser Web Speech API |
| **Azure Translator** | Real-time question/answer translation (100+ languages) | NLP | GPT translation fallback |
| **Azure Maps** | ETA with live traffic, nearest hospital routing | Plan & Manage | Haversine + 440-hospital DB |
| **Azure Content Safety** | Filter harmful input from patients | Responsible AI | Local allowlist filter |

> **Resilience first.** Every Azure service has a tested graceful fallback — the system works fully offline with zero credentials configured.

<br/>

## 🧬 AI Clinical Question Engine

The heart of CodeZero is its **condition-specific question generation** — a significant improvement over generic symptom checklists.

### How questions are generated

```
Chief Complaint (English)
         │
         ▼
  ┌──────────────┐
  │  RAG Search  │ ◀── Azure AI Search (medical guidelines)
  │  Guidelines  │
  └──────────────┘
         │ context injected into prompt
         ▼
  ┌───────────────────────────────────────────────────────┐
  │  GPT System Prompt — 5 mandatory question slots:      │
  │                                                       │
  │  Q1 → Worst-case RED FLAG rule-out for THIS complaint │
  │  Q2 → Character / quality of the main symptom        │
  │  Q3 → Onset, timing, or trigger SPECIFIC to complaint│
  │  Q4 → Associated symptom diagnostically significant  │
  │  Q5 → Medical background relevant ONLY to complaint  │
  │                                                       │
  │  + Demographics adaptation (age, sex)                 │
  │  + Forbidden generics list                            │
  └───────────────────────────────────────────────────────┘
         │
         ▼
  JSON parse (robust extraction from prose)
         │
         ▼
  Azure Translator → patient's language
         │
         ▼
  Patient sees targeted, clickable questions
```

### Condition-specific mock protocols (offline fallback)

When the AI is unavailable, 13 hand-crafted clinical protocols activate automatically:

| Complaint Group | Key Assessment Focus |
|:---|:---|
| Chest / Cardiac | Radiation pattern, diaphoresis, STEMI timing, cardiac history |
| Head / Stroke (FAST) | Sudden onset, facial droop, arm weakness, speech, time window |
| Abdominal / GI | Pain location, peritonitis signs, bowel changes, surgical history |
| Respiratory / Breathing | SpO2 proxy (cyanosis), wheeze, triggering exposure, asthma history |
| Back Pain | Radiation to leg, cauda equina red flags, mechanism, neuro signs |
| Leg Pain / DVT | Swelling/warmth, recent surgery/travel, injury vs. spontaneous |
| Arm / Shoulder | Mechanism, ROM, neurovascular compromise, deformity |
| Fever / Sepsis | Temperature grade, meningism signs, UTI, travel/exposure |
| Dizziness / Syncope | Vertigo vs. presyncope, loss of consciousness, orthostatic |
| Allergy / Anaphylaxis | Airway threat (lip/throat), trigger, development speed, bronchospasm |
| Trauma / Injury | Mechanism, body region, bleeding control, head LOC |
| Eye Emergency | Vision loss (sudden), chemical exposure, floaters, redness |
| Urinary / Renal | Dysuria, flank pain, fever, stone/UTI history |
| Neck Pain | Meningismus test, trauma, headache+fever combo, radiculopathy |
| Diabetes | Type, glucose level, DKA signs, medication compliance |

<br/>

## 🗺️ Real-Time Patient Tracking

The patient app continuously streams GPS coordinates to the ER dashboard:

```javascript
// Patient side — runs every 4 seconds
navigator.geolocation.watchPosition(async position => {
    await fetch(`/api/patient/${regNumber}/location`, {
        method: 'PATCH',
        body: JSON.stringify({ lat, lon, eta_minutes })
    });
});
```

```python
# Server endpoint
@app.patch("/api/patient/{patient_id}/location")
def update_location(patient_id: str, body: LocationUpdate):
    # lat/lon rounded to ~111m grid (GDPR)
    hq.update_patient_location(patient_id, rounded_lat, rounded_lon)
```

The ER Leaflet map refreshes the pin positions every 5 seconds — giving staff a live operational picture of all en-route patients with colour-coded triage severity.

<br/>

## 🏥 ER Command Center — Dashboard Features

### Screenshots

<div align="center">

**Incoming Patients — Emergency Alert + Triage Cards**
<img src="docs/images/ss_dashboard_1_incoming.png" width="85%" alt="ER Command Center — Incoming patient list with emergency alert banner"/>

<br/>

**Patient Detail — Clinical Dossier (This Visit tab)**
<img src="docs/images/ss_dashboard_2_detail.png" width="85%" alt="Expanded patient card with clinical details, voice transcript, and AI risk flags"/>

<br/>

| Live GPS Tracking Map | Real-Time Statistics |
|:---:|:---:|
| <img src="docs/images/ss_dashboard_3_tracking.png" width="420" alt="Leaflet map with triage-coloured patient pins and ETA sidebar"/> | <img src="docs/images/ss_dashboard_4_stats.png" width="420" alt="Live statistics — triage breakdown, avg risk, GPS tracked count"/> |

</div>

### Patient Card System
- Smart diff rendering — cards update in-place (no flicker on refresh)
- Expandable detail panel with 4 tabs: **Overview**, **Q&A Transcript**, **Clinical AI Report**, **Media**
- Medical history pulled from health DB (ICD-10 codes, medications, allergies, labs)
- Patient-facing AI summary (`patient_summary`) **and** English clinical report (`patient_summary_en`) — always shown in English for staff

### Sorting & Filtering
| Control | Behaviour |
|:---|:---|
| **By Triage** | EMERGENCY → URGENT → ROUTINE (database-level ordering) |
| **By ETA** | Ascending arrival time — soonest first |
| **By Risk** | Descending risk score (AI-assessed 0–10) |
| **Newest** | Most recently registered patient first |
| KPI Filters | Click any KPI card to filter by Emergencies, Urgents, Routines, En Route, In Treatment, Discharged, or All |

> Sort mode persists across KPI filter changes — clicking "By ETA" while viewing "All Patients" correctly re-sorts the full list.

### Emergency Alert System
When a new EMERGENCY-level patient registers, the dashboard triggers:
- Full-width crimson banner with animated pulse effect
- Patient name, complaint, and ETA prominently displayed
- Auto-dismisses after 10 seconds or on manual close

### Additional Panels
- **Live Map** — Leaflet map with patient pins, colour-coded by triage; dark/light tile switching
- **Statistics** — Real-time charts: triage breakdown, top conditions, hourly arrivals
- **Reports** — Printable/PDF-ready patient reports
- **Dark Mode** — One-click toggle with instant map tile swap (no reload)
- **Keyboard Navigation** — Arrow keys, Enter (expand), Escape (collapse) on patient list
- **Compact Mode** — Toggle between full and condensed card view

<br/>

## 📱 Patient App — VitalNavAI

### Screenshots

<div align="center">

| Language Selection | Welcome Screen |
|:---:|:---:|
| <img src="docs/images/ss_patient_1_lang.png" width="220" alt="Language selection — EN / DE / TR"/> | <img src="docs/images/ss_patient_2_welcome.png" width="220" alt="Welcome screen with AI status"/> |

| Symptom Grid | Chest Pain Selected |
|:---:|:---:|
| <img src="docs/images/ss_patient_3_input.png" width="220" alt="Voice mic + symptom grid"/> | <img src="docs/images/ss_patient_3b_selected.png" width="220" alt="Chest Pain symptom highlighted"/> |

| Photo Upload | AI Question Engine |
|:---:|:---:|
| <img src="docs/images/ss_patient_4_photos.png" width="220" alt="Optional photo/video upload"/> | <img src="docs/images/ss_patient_5_questions.png" width="220" alt="AiVoN generating personalised questions"/> |

</div>

### Design Principles
- **Zero friction** — voice-first; patients in distress don't type
- **Touch-optimised** — all interactive elements ≥ 54 px
- **Mobile-only layout** — centred 480px card, full-screen on phones
- **Calm clinical palette** — Medical Teal primary, clear EMERGENCY/URGENT/ROUTINE distinction

### Multi-Language Support
| Language | Code | Direction |
|:---|:---|:---:|
| English | `en` | LTR |
| German / Deutsch | `de` | LTR |
| Turkish / Türkçe | `tr` | LTR |

### Photo Upload
Patients can upload images or videos of their injury, rash, or affected area. Media is stored server-side and accessible in the dashboard's media tab with a lightbox viewer (keyboard navigation: ←→ arrows, Escape to close).

### Consent & Privacy
Before submission, patients review a clear consent screen explaining what data is collected, how it is used, and how long it is stored — consistent with GDPR Article 7.

<br/>

## 🗄️ Hospital Database

Ships with a comprehensive pre-loaded emergency hospital database — no external API needed for discovery:

| Country | Hospitals | Coverage |
|:---|:---:|:---|
| 🇩🇪 Germany | **232** | All 16 Bundesländer at district level |
| 🇬🇧 United Kingdom | **121** | England, Scotland, Wales, Northern Ireland — major NHS A&E |
| 🇹🇷 Turkey | **87** | All major provinces — university, city, and training hospitals |
| **Total** | **440** | |

**Smart ranking formula:**

```python
effective_eta = travel_time_minutes + occupancy_penalty(low=0, medium=+10, high=+25, full=+60)
```

Evaluates up to **10 candidates** within 150 km and returns the **top 3** sorted by effective ETA — patients reach the best *available* hospital, not just the nearest one.

<br/>

## 🩺 Health Records Database

**30 richly detailed demo patient records** (10 per country) with full clinical depth:

<table>
<tr>
<td>

**🇩🇪 10 German Patients**
- Coronary artery disease
- Type 1 diabetes (insulin pump)
- COPD, migraine with aura
- Atrial fibrillation + pacemaker
- Anaphylaxis (EpiPen carrier)

</td>
<td>

**🇹🇷 10 Turkish Patients**
- Diabetic nephropathy
- Rheumatoid arthritis
- Post-CABG coronary disease
- Epilepsy, Parkinson's disease
- Hashimoto thyroiditis

</td>
<td>

**🇬🇧 10 UK Patients**
- Heart failure (EF 40%)
- Status asthmaticus history
- COPD + T2DM multi-morbidity
- Crohn's disease on immunosuppression
- Bipolar disorder on lithium

</td>
</tr>
</table>

Each record includes: **demographics** · **ICD-10 diagnoses** · **active medications** · **lab results** · **vitals** · **allergies** · **visit history** · **emergency contacts**

Health records are matched to incoming patients by health card number — giving ER staff instant access to critical history at the point of notification.

<br/>

## 🔌 API Reference

| Endpoint | Method | Description |
|:---|:---:|:---|
| `/api/patient/questions` | `POST` | Generate condition-specific clinical follow-up questions |
| `/api/patient/assess` | `POST` | Full triage assessment — returns level, risk score, AI report |
| `/api/patient/submit` | `POST` | Register patient in hospital queue |
| `/api/patient/hospitals` | `GET` | Nearest hospitals ranked by effective ETA |
| `/api/patient/{id}/location` | `PATCH` | Update live GPS location (called every 4s by app) |
| `/api/transcribe` | `POST` | Audio blob → transcribed text via Azure Speech |
| `/api/patients` | `GET` | Patient list with `sort` and `status` filters |
| `/api/stats` | `GET` | Queue KPIs (totals, emergencies, en-route count) |
| `/api/patient/{id}` | `GET` | Single patient full detail |
| `/api/health_record/{number}` | `GET` | Health DB lookup by patient card number |
| `/api/illness_photo/{id}/{idx}` | `GET` | Retrieve uploaded patient photo or video |
| `/api/tracking` | `GET` | All en-route patients with GPS data for map |
| `/api/ai-status` | `GET` | AI engine health (initialized, model, mode) |

<br/>

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+**
- Azure subscription *(optional — full demo mode works without any credentials)*

### 1. Clone & Install

```bash
git clone https://github.com/AtamerErkal/CodeZero.git
cd CodeZero
python -m venv .venv

# Linux / macOS
source .venv/bin/activate

# Windows
.venv\Scripts\activate

pip install -r requirements.txt
```

### 2. Configure Environment *(optional — skip for demo mode)*

```bash
cp .env.example .env
```

<details>
<summary><b>📋 Environment Variables</b> (click to expand)</summary>

```env
# ── Azure OpenAI ──────────────────────────────────
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_KEY=your-key
AZURE_OPENAI_API_VERSION=2024-12-01-preview
GPT_DEPLOYMENT=your-deployment-name     # exact name in Azure OpenAI Studio

# ── Azure AI Search ───────────────────────────────
SEARCH_ENDPOINT=https://your-search.search.windows.net
SEARCH_KEY=your-key
SEARCH_INDEX_NAME=medical-knowledge-index

# ── Azure Speech ──────────────────────────────────
SPEECH_KEY=your-key
SPEECH_REGION=westeurope

# ── Azure Translator ──────────────────────────────
TRANSLATOR_KEY=your-key
TRANSLATOR_ENDPOINT=https://api.cognitive.microsofttranslator.com
TRANSLATOR_REGION=global

# ── Azure Maps ────────────────────────────────────
MAPS_SUBSCRIPTION_KEY=your-key          # optional — haversine used as fallback

# ── Optional Services ─────────────────────────────
DOCUMENT_INTELLIGENCE_ENDPOINT=https://your-doc-intel.cognitiveservices.azure.com/
DOCUMENT_INTELLIGENCE_KEY=your-key
CONTENT_SAFETY_ENDPOINT=https://your-content-safety.cognitiveservices.azure.com/
CONTENT_SAFETY_KEY=your-key

# ── Hospital Identity ─────────────────────────────
HOSPITAL_NAME=City General Hospital
HOSPITAL_LOCATION_LAT=48.7758
HOSPITAL_LOCATION_LON=9.1829
```

</details>

### 3. Index Medical Guidelines *(one-time, optional)*

```bash
python setup_index.py
```

Processes `data/medical_guidelines/*.txt`, chunks documents, and uploads to Azure AI Search with semantic configuration. Skipped gracefully without credentials.

### 4. Start the Server

```bash
python hospital_server_v1.py
# → http://localhost:8001
```

### 5. Open the Apps

| App | How to Open | Who Uses It |
|:---|:---|:---|
| 📱 **VitalNavAI** Patient App | Open `ui/patient_app_v12.html` in browser | Patient — pre-hospital triage |
| 🏥 **ER Command Center** | `http://localhost:8001` | ER staff — live patient management |

> Both HTML files are **fully standalone** — zero build step, no npm, no framework. Open directly in any modern browser.

<br/>

## 🧪 Demo Mode

CodeZero runs completely without Azure credentials — ideal for evaluation and development:

| Feature | ☁️ With Azure | 🖥️ Demo Mode |
|:---|:---|:---|
| Triage reasoning | GPT-4/5 + RAG guidelines | Rule-based keyword engine |
| Question generation | GPT — condition-specific | 13 clinical protocol sets |
| Translation | Azure Translator (100+ languages) | GPT fallback / passthrough |
| Voice input | Azure Speech STT + lang detect | Browser Web Speech API |
| Hospital search | Azure Maps POI + live traffic | Built-in 440-hospital database |
| ETA calculation | Real-time traffic data | Haversine formula + 55 km/h estimate |
| Knowledge search | Azure AI Search semantic | Local file keyword matching |
| GPS tracking | Real device geolocation | Simulation mode (auto-moving pin) |

<br/>

## 🎬 Demo Scenarios

### Scenario 1 — 🚨 Chest Pain → EMERGENCY

```
1. Open patient app → speak or click "Chest Pain"
2. Answer: pain radiates to jaw, severity 9/10, sweating, shortness of breath
3. → EMERGENCY — Suspected Acute Coronary Syndrome / STEMI
   Dashboard: alert banner fires, patient card appears, countdown timer starts
```

### Scenario 2 — 🦵 Leg Swelling → URGENT (DVT)

```
1. Speak: "My leg is swollen and red since my flight yesterday"
2. Auto-detected language, complaint_en = "leg swelling after flight"
3. AI questions: Is it warm? Any recent surgery? Previous DVT?
4. → URGENT — Suspected Deep Vein Thrombosis
```

### Scenario 3 — ⚡ Stroke Symptoms → EMERGENCY

```
1. Click "Stroke / Face drooping"
2. FAST assessment: sudden onset, facial asymmetry, arm drift, slurred speech
3. Onset < 30 min → within thrombolysis window
4. → EMERGENCY — Possible Ischaemic Stroke (FAST positive, time-critical)
```

### Scenario 4 — 🇩🇪 German Voice Input

```
1. Select Deutsch or speak — language auto-detected
2. "Ich habe starke Kopfschmerzen und mir ist schwindelig"
3. Translated to English internally: "I have severe headache and dizziness"
4. AI questions served in German, assessment runs in English
5. → URGENT — Severe migraine with vascular features
```

### Scenario 5 — 💊 Mild Complaint → ROUTINE

```
1. "Sore throat since 2 days, no fever, no difficulty swallowing"
2. Severity 2/10, improving, no red flags
3. → ROUTINE — Viral pharyngitis, self-care advice
```

<br/>

## 📁 Project Structure

```
CodeZero/
├── 📄 hospital_server_v1.py          # FastAPI REST server — 14 endpoints (1,505 lines)
├── 📄 requirements.txt
│
├── 📂 src/
│   ├── triage_engine.py              # 🧠 Core AI — GPT + RAG + 13 mock protocols (2,254 lines)
│   ├── hospital_queue.py             # 🏥 SQLite patient queue — GDPR-compliant
│   ├── maps_handler.py               # 🗺️ 440-hospital DB + ETA routing (755 lines)
│   ├── speech_handler.py             # 🎙️ Azure Speech STT + auto language detection
│   ├── translator.py                 # 🌍 Azure Translator — bidirectional, 100+ languages
│   ├── knowledge_indexer.py          # 📚 Azure AI Search — index + semantic RAG
│   ├── document_processor.py         # 📄 Azure Doc Intelligence — PDF extraction
│   ├── health_db.py                  # 💊 Health records — 30 demo patients (DE/TR/UK)
│   └── safety_filter.py              # 🛡️ Azure Content Safety input filtering
│
├── 📂 ui/
│   ├── patient_app_v12.html          # 📱 VitalNavAI — standalone patient triage app
│   └── hospital_dashboard_v9.html    # 📊 ER Command Center — standalone dashboard
│
├── 📂 data/
│   └── medical_guidelines/           # 📋 Clinical protocols (chest pain, stroke, DVT, ...)
│
└── 📂 docs/
    └── images/                       # Architecture diagrams, banner, demo screenshots
```

<br/>

## 🏛️ Design Principles

| Principle | Implementation |
|:---|:---|
| **⚡ Speed** | < 5 s per interaction; 440-hospital DB for instant lookup; smart diff card updates (no full re-render) |
| **🎯 Clinical Relevance** | Every AI question is complaint-specific; forbidden generic questions; NICE/AHA guideline grounding |
| **🔬 Transparency** | Every triage assessment cites source guidelines; RAG-grounded responses; clinical rationale per question |
| **🔒 Privacy** | GDPR-compliant: GPS rounded to ~1 km; no PII stored; random anonymous patient IDs |
| **📱 Mobile-First** | 480px centred card; ≥ 54 px touch targets; voice input as primary input method |
| **🌍 Multilingual** | 10 languages auto-detected; full RTL layout for Arabic/Hebrew/Farsi |
| **🛡️ Resilience** | Every Azure service has a tested fallback; zero dependencies for core offline operation |
| **📦 Portability** | HTML files are 100% standalone — open directly in any browser, no build step, no server needed for patient app |

<br/>

## 💰 Cost Estimates

<details>
<summary><b>Azure API cost breakdown per patient</b> (click to expand)</summary>

| Service | Typical Usage | Unit Cost | Per Patient |
|:---|:---|---:|---:|
| Azure OpenAI GPT-4 input | ~1,200 tokens/session | $0.03 / 1K | ~$0.036 |
| Azure OpenAI GPT-4 output | ~800 tokens/session | $0.06 / 1K | ~$0.048 |
| Azure Translator | ~500 chars/session | $10 / 1M | ~$0.005 |
| Azure Speech STT | ~30 sec voice input | $1.00 / hour | ~$0.008 |
| Azure Maps Route | 1 ETA request | $0.50 / 1K | ~$0.001 |
| **Total per patient** | | | **~$0.10** |

**Estimated monthly cost @ 100 patients/day: ~$300/month**

*Costs will differ significantly for GPT-5.x models. Check Azure OpenAI pricing page for current rates.*

</details>

<br/>

---

<div align="center">

**Built with ❤️ using Azure AI Services**

<sub>Integrating Azure OpenAI · Azure AI Search · Azure Speech · Azure Translator · Azure Maps · Azure Document Intelligence · Azure Content Safety</sub>

<br/>

[⬆ Back to Top](#-codezero)

</div>
