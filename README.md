# ⚡ CodeZero — Intelligent Pre-Hospital Triage System

An AI-powered pre-hospital emergency triage web application that enables patients
to receive intelligent triage assessment **before** arriving at the hospital.

> ⚠️ **Medical Disclaimer:** This is an educational/demonstration system.
> It is **NOT** a certified medical device and must **NOT** be used for real
> triage decisions. Always call emergency services (112 / 911) for genuine
> medical emergencies.

---

## Table of Contents

- [Core Innovation](#core-innovation)
- [Architecture](#architecture)
- [Azure Services Used](#azure-services-used)
- [Project Structure](#project-structure)
- [Hospital Database](#hospital-database)
- [Setup Instructions](#setup-instructions)
- [Running the Applications](#running-the-applications)
- [Demo Usage Guide](#demo-usage-guide)
- [Patient Journey](#patient-journey)
- [API Cost Estimates](#api-cost-estimates)
- [Design Principles](#design-principles)

---

## Core Innovation

Unlike existing symptom checkers (Symptomate, Isabel, Infermedica), CodeZero offers:

1. **Proactive Hospital Notification** — ER receives patient data + ETA *before* arrival
2. **Voice-First + Auto Language Detection** — Patient speaks in any language; system auto-detects and continues in that language (10 languages, RTL supported)
3. **Dynamic Interactive Questioning** — AI-generated follow-up questions grounded in medical guidelines via RAG
4. **Real-Time Routing** — Azure Maps integration for ETA calculation with live traffic data; haversine fallback when offline
5. **Comprehensive Hospital Database** — 440 pre-loaded emergency hospitals across Germany, UK and Turkey with coordinates and addresses
6. **ER Preparation Dashboard** — Hospital staff see incoming patients with countdown timers and pre-arrival checklists

---

## Architecture

```
+----------------------------------------------------------------------+
|                    PATIENT (Mobile / Web Browser)                    |
|   Voice Input > Language Detection > Dynamic Questions > ETA > Done  |
+------------------------+---------------------------------------------+
                         |
          +--------------+--------------+
          |                             |
   +------+------+              +-------+------+
   | patient_    |              |  Flask API   |
   | app.html    |<------------>|  hospital_   |
   | (standalone)|   REST API   |  server.py   |
   +-------------+              +-------+------+
                                        |
        +-------------------------------+-----------------------+
        |                               |                       |
+-------+------+          +-------------+----------+   +-------+------+
| Azure Speech |          |    Azure OpenAI         |   | Azure Maps   |
| STT + Auto   |          |  GPT-4 + RAG pipeline  |   | ETA + Route  |
| Lang Detect  |          |  (triage_engine.py)    |   | (fallback:   |
+--------------+          +-------------+----------+   | haversine)   |
                                        |               +--------------+
                          +-------------+-----------+
                          |   Azure AI Search        |
                          |  Medical KB Index        |
                          |  Semantic Ranking        |
                          +-------------+-----------+
                                        |
                          +-------------+-----------+
                          |   Azure Translator       |
                          |   100+ Languages         |
                          +-------------+-----------+
                                        |
                          +-------------+-----------+
                          |  Hospital Queue          |
                          |  (SQLite - anonymized)   |
                          +-------------+-----------+
                                        |
                          +-------------+-----------+
                          |   ER DASHBOARD           |
                          | hospital_dashboard.html  |
                          |  (staff view)            |
                          +-------------------------+
```

---

## Azure Services Used

| Service | Purpose | AI-102 Domain |
|---|---|---|
| Azure OpenAI (GPT-4) | Conversational AI, triage reasoning, question generation | Generative AI |
| Azure AI Search | Medical knowledge base, semantic search, RAG retrieval | Knowledge Mining |
| Azure AI Document Intelligence | Extract text from medical PDFs / guidelines | Knowledge Mining |
| Azure Speech Services | Voice input with automatic language detection | NLP |
| Azure Translator | Patient <> English translation (100+ languages) | NLP |
| Azure Maps | ETA calculation, nearest hospital routing | Plan & Manage |
| Azure Content Safety | Filter harmful content from patient input (optional) | Responsible AI |

---

## Project Structure

```
CodeZero/
├── .env                          # Azure credentials (never commit)
├── .gitignore
├── README.md
├── requirements.txt
├── hospital_server.py            # Flask REST API — 5 endpoints
├── setup_index.py                # One-time indexing: process + upload guidelines
├── data/
│   └── medical_guidelines/
│       ├── chest_pain_protocol.txt
│       ├── stroke_protocol.txt
│       ├── diabetic_emergency.txt
│       ├── trauma_protocol.txt
│       └── respiratory_emergency.txt
├── src/
│   ├── __init__.py
│   ├── document_processor.py     # Azure Document Intelligence — PDF extraction
│   ├── knowledge_indexer.py      # Azure AI Search — index + semantic search
│   ├── speech_handler.py         # Azure Speech — STT + auto language detection
│   ├── translator.py             # Azure Translator — multilingual support
│   ├── triage_engine.py          # Core AI logic — OpenAI + RAG + mock fallback
│   ├── maps_handler.py           # Hospital DB (440 hospitals) + ETA calculation (701 lines)
│   ├── safety_filter.py          # Azure Content Safety (optional)
│   ├── health_db.py              # Health records database layer
│   └── hospital_queue.py         # SQLite patient queue (GDPR-compliant)
├── ui/
│   ├── patient_app.html          # Standalone HTML patient app
│   ├── patient_app.py            # Streamlit patient app — alternative
│   ├── hospital_dashboard.html   # Standalone HTML ER dashboard
│   └── hospital_dashboard.py     # Streamlit ER dashboard — alternative
└── tests/
    ├── __init__.py
    └── test_scenarios.py         # Automated test scenarios
```

---

## Hospital Database

`src/maps_handler.py` contains a comprehensive pre-loaded emergency hospital database
covering three countries at district/regional level. Azure Maps is used for real-time
ETA when configured; the haversine formula provides instant fallback estimates otherwise.

| Country | Hospitals | Coverage |
|---|---|---|
| Germany | **232** | All 16 Bundesländer — district level (incl. Ulm, Neu-Ulm, Dillingen, Donauwörth, Günzburg and all surrounding areas) |
| United Kingdom | **121** | England, Scotland, Wales, Northern Ireland — all major NHS Emergency Departments |
| Turkey | **87** | All major provinces — university hospitals, city hospitals, training & research hospitals |
| **Total** | **440** | — |

**Hospital ranking formula:**

```
effective_eta = travel_time_minutes + occupancy_penalty
```

| Occupancy | Penalty |
|---|---|
| Low | 0 min |
| Medium | +10 min |
| High | +25 min |
| Full | +60 min |

The system returns the **top 3 hospitals** sorted by effective ETA, ensuring patients
are routed to the best available facility — not just the geographically closest one.
Search radius is 150 km; up to 10 candidates are evaluated before ranking.

---

## Setup Instructions

### Prerequisites

- Python 3.11+
- Azure subscription with the following services provisioned:
  - Azure OpenAI (GPT-4 deployment)
  - Azure AI Search (Basic tier or above for semantic ranking)
  - Azure AI Document Intelligence
  - Azure Speech Services
  - Azure Translator
  - Azure Maps
  - Azure Content Safety (optional)

### 1. Clone and Install

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

### 2. Configure Environment

Copy the template and fill in your Azure credentials:

```bash
cp .env.example .env   # or edit .env directly
```

Required keys:

```bash
# Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_KEY=your-key
AZURE_OPENAI_API_VERSION=2024-12-01-preview
GPT_DEPLOYMENT=your-gpt4-deployment-name

# Azure AI Search
SEARCH_ENDPOINT=https://your-search.search.windows.net
SEARCH_KEY=your-key
SEARCH_INDEX_NAME=medical-knowledge-index

# Azure Speech
SPEECH_KEY=your-key
SPEECH_REGION=westeurope

# Azure Translator
TRANSLATOR_KEY=your-key
TRANSLATOR_ENDPOINT=https://api.cognitive.microsofttranslator.com
TRANSLATOR_REGION=global

# Azure Maps (optional — haversine fallback used if not set)
MAPS_SUBSCRIPTION_KEY=your-key

# Optional
DOCUMENT_INTELLIGENCE_ENDPOINT=https://your-doc-intel.cognitiveservices.azure.com/
DOCUMENT_INTELLIGENCE_KEY=your-key
CONTENT_SAFETY_ENDPOINT=https://your-content-safety.cognitiveservices.azure.com/
CONTENT_SAFETY_KEY=your-key

# Hospital config
HOSPITAL_NAME=City General Hospital
HOSPITAL_LOCATION_LAT=48.7758
HOSPITAL_LOCATION_LON=9.1829
```

> **Note:** `GPT_DEPLOYMENT` must match your **exact deployment name** in Azure OpenAI Studio,
> not the model name. Example: if you named your deployment `gpt4-prod`, use that value.

### 3. Index Medical Guidelines (one-time)

```bash
python setup_index.py
```

This will:
1. Read all `.txt` files from `data/medical_guidelines/`
2. Chunk documents (1000 chars, 200-char overlap)
3. Create / update the Azure AI Search index with semantic configuration
4. Upload all chunks

> Without Azure AI Search credentials, the script exits cleanly and the app
> falls back to local keyword search automatically at runtime.

### 4. Run the Flask API

```bash
python hospital_server.py
```

Starts on `http://localhost:5000`

| Endpoint | Method | Description |
|---|---|---|
| `/api/transcribe` | POST | Audio to text via Azure Speech |
| `/api/questions` | POST | Generate triage follow-up questions |
| `/api/assess` | POST | Full triage assessment |
| `/api/hospitals` | POST | Find nearest hospitals with ETA |
| `/api/submit` | POST | Submit patient to hospital queue |

### 5. Open the Patient App

Open `ui/patient_app.html` directly in any browser — no server needed.
The app communicates with the Flask API above.

Alternatively run the Streamlit version:

```bash
streamlit run ui/patient_app.py
# Opens at http://localhost:8501
```

### 6. Open the Hospital Dashboard

Open `ui/hospital_dashboard.html` directly in any browser — no server needed.

Alternatively run the Streamlit version:

```bash
streamlit run ui/hospital_dashboard.py --server.port 8502
# Opens at http://localhost:8502
```

---

## Demo Usage Guide

The system runs in **demo mode** with no Azure credentials. In demo mode:

| Feature | With Azure | Demo Mode |
|---|---|---|
| Triage logic | GPT-4 + RAG | Rule-based keyword engine |
| Translation | Azure Translator | Passthrough (original text) |
| Voice input | Azure Speech STT | Not available |
| Hospital search | Azure Maps POI | Built-in 440-hospital DB |
| ETA calculation | Real-time traffic | Haversine + 55 km/h estimate |
| Knowledge search | Azure AI Search | Local file keyword matching |

### Quick Demo Scenarios

**Scenario 1 — Chest Pain → EMERGENCY**
1. Click **Chest Pain** on the input page
2. Answer questions: Yes to radiation, 8+ on pain scale, select Sweating + Shortness of breath
3. Expected result: EMERGENCY — Suspected Acute Coronary Syndrome

**Scenario 2 — Mild Headache → ROUTINE**
1. Click **Mild Headache**
2. Answer: Days ago, severity 3, No to all checkboxes
3. Expected result: ROUTINE — Self-care advised

**Scenario 3 — Stroke Symptoms → EMERGENCY**
1. Click **Stroke Symptoms**
2. Answer FAST questions: Sudden onset Yes, Face symmetry No, Arms No, Speech Yes
3. Expected result: EMERGENCY — Possible Stroke (FAST positive)

**Scenario 4 — German Patient (multilingual)**
1. Click **Demo Deutsch**
2. System detects German, continues in German
3. Questions shown in German; backend processes in English

**Scenario 5 — Arabic Patient (RTL layout)**
1. Click **Demo Arabic**
2. System detects Arabic; UI switches to right-to-left layout
3. Demonstrates RTL language support

### Hospital Dashboard

1. Open `ui/hospital_dashboard.html` in a second browser tab
2. Use **Admin > Add Test Emergency** to inject a test patient
3. Watch the countdown timer count down
4. Use **Arrived > Treating > Discharge** to move through statuses
5. Dashboard auto-refreshes every 60 seconds

---

## Patient Journey

```
1.  Patient opens app (any device, any language)
2.  Types or speaks symptoms
3.  System auto-detects language (10 supported, including RTL)
4.  AI generates 3-5 targeted follow-up questions (RAG-grounded)
5.  Patient answers questions
6.  AI performs triage assessment (EMERGENCY / URGENT / ROUTINE)
7.  Patient shares GPS location — nearest hospitals found within 150 km
8.  Top 3 hospitals ranked by effective ETA (travel time + occupancy penalty)
9.  Patient selects hospital — hospital ER notified instantly
10. ER dashboard shows countdown timer + pre-arrival prep checklist
11. Staff prepare for patient arrival
```

---

## API Cost Estimates

Estimates based on Azure pricing as of early 2026. Actual costs vary by region and usage.

| Service | Unit | Estimated Cost |
|---|---|---|
| Azure OpenAI GPT-4 (input) | per 1K tokens | ~$0.03 |
| Azure OpenAI GPT-4 (output) | per 1K tokens | ~$0.06 |
| Typical triage session | ~2,000 tokens total | ~$0.09 per patient |
| Azure AI Search | per 1K queries | ~$0.005 |
| Azure Translator | per 1M characters | ~$10.00 |
| Azure Speech STT | per audio hour | ~$1.00 |
| Azure Maps Route | per 1K requests | ~$0.50 |

**Estimated monthly cost (100 patients/day):**
- Triage AI calls: ~$270/month
- Supporting services: ~$30/month
- **Total estimate: ~$300/month**

> Token usage is logged per API call. Monitor with Azure Cost Management alerts.
> Hospital search uses the built-in 440-hospital DB first; Azure Maps is only
> called for precise real-time ETA when MAPS_SUBSCRIPTION_KEY is configured.

---

## Design Principles

| Principle | Implementation |
|---|---|
| **Speed** | < 5 sec per interaction; 440-hospital DB for instant nearby search; cached translations |
| **Simplicity** | Max 5 questions; large touch targets (54px buttons); minimal UI |
| **Trust** | All assessments cite medical guideline sources |
| **Privacy** | GDPR compliant: GPS rounded to ~1 km grid before storage; no names stored |
| **Mobile-First** | Centered 720px layout; 54px buttons; audio input support |
| **Multilingual** | 10 languages auto-detected; RTL layout for Arabic/Hebrew/Farsi |
| **Resilience** | Every Azure service has a fallback; app never crashes on missing credentials |
| **Portability** | patient_app.html and hospital_dashboard.html are fully standalone — open directly in any browser with no build step |