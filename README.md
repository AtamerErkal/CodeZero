<div align="center">

<img src="docs/images/banner.png" alt="CodeZero Banner" width="100%"/>

<br/>

# ⚡ CodeZero

### Intelligent Pre-Hospital Triage System

**AI-powered emergency triage that saves critical minutes between symptoms and treatment.**

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Azure AI](https://img.shields.io/badge/Azure_AI-0078D4?style=for-the-badge&logo=microsoftazure&logoColor=white)](https://azure.microsoft.com/en-us/products/ai-services)
[![GPT-4](https://img.shields.io/badge/GPT--4-412991?style=for-the-badge&logo=openai&logoColor=white)](https://openai.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-22c55e?style=for-the-badge)](LICENSE)

[🚀 Quick Start](#-quick-start) · [📖 How It Works](#-how-it-works) · [🎯 Features](#-key-features) · [🏗️ Architecture](#%EF%B8%8F-architecture) · [🎬 Demo](#-demo-scenarios)

---

</div>

> [!CAUTION]
> **Medical Disclaimer** — This is an educational/demonstration system. It is **NOT** a certified medical device and must **NOT** be used for real triage decisions. Always call emergency services (**112** / **911**) for genuine medical emergencies.

<br/>

## 🧠 What is CodeZero?

**CodeZero** is a full-stack AI-powered pre-hospital triage system that assesses patients *before* they arrive at the emergency room. It bridges the critical gap between the moment symptoms begin and the moment treatment starts — enabling hospitals to prepare for incoming patients in real-time.

<div align="center">
<img src="" alt="CodeZero Patient App and Hospital Dashboard" width="90%"/>
<br/><br/>
</div>

Unlike traditional symptom checkers that end with a generic recommendation, CodeZero creates a **live connection** between the patient and the hospital — the ER team sees who's coming, what's wrong, and how long until they arrive.

<br/>

## ✨ Key Features

<table>
<tr>
<td width="50%">

### 🎙️ Voice-First, Any Language
Patients speak in their native language — the system **auto-detects** from 10 supported languages (including RTL for Arabic, Hebrew, and Farsi) and continues the conversation seamlessly. No dropdowns, no language barriers.

### 🧬 AI-Powered Dynamic Questioning
GPT-4 generates **clinically relevant follow-up questions** grounded in real medical guidelines via RAG (Retrieval-Augmented Generation). Every question adapts based on previous answers.

### 🏥 Proactive Hospital Notification
The ER dashboard receives patient data, triage level, and ETA **before arrival** — giving staff time to prepare equipment, allocate beds, and review medical history.

</td>
<td width="50%">

### 🗺️ Real-Time Smart Routing
Finds the best hospital based on **effective ETA** — not just distance. Factors in real-time traffic (Azure Maps) and hospital occupancy to route patients to where they'll be treated fastest.

### 📋 440 Pre-Loaded Hospitals
Comprehensive emergency hospital database covering **Germany** (232), **United Kingdom** (121), and **Turkey** (87) at district level. Instant nearest-hospital search with no API dependency.

### 🔒 GDPR-Compliant by Design
GPS coordinates are rounded to ~1 km grid before storage. No names stored. Patient IDs are random ER codes. Privacy is not an afterthought — it's baked into every layer.

</td>
</tr>
</table>

<br/>

## 🎯 How It Works

```
  ╭───────────────────────────────────────────────────────────────────╮
  │                    THE PATIENT JOURNEY                            │
  ╰───────────────────────────────────────────────────────────────────╯

  ┌─────────┐     ┌──────────┐     ┌──────────┐     ┌──────────────┐
  │ 🗣️ SPEAK │ ──▶ │ 🌍 DETECT │ ──▶ │ 🤖 ASSESS │ ──▶ │ 🏥 ROUTE     │
  │ or TYPE  │     │ LANGUAGE │     │ TRIAGE   │     │ TO HOSPITAL  │
  └─────────┘     └──────────┘     └──────────┘     └──────────────┘
       │                │                │                │
       ▼                ▼                ▼                ▼
  "I have chest    Auto-detected:   3-5 targeted     Top 3 hospitals
   pain and I'm    🇩🇪 German        follow-up Qs     by effective ETA
   sweating"       → continues      from GPT-4 +     (travel time +
                   in Deutsch       medical KB        occupancy)
                                         │
                                         ▼
                                  ┌──────────────┐
                                  │ 📊 TRIAGE     │
                                  │  EMERGENCY    │──▶ 🚨 ER NOTIFIED
                                  │  URGENT       │    Countdown timer
                                  │  ROUTINE      │    Prep checklist
                                  └──────────────┘    Medical history
```

<br/>

## 🏗️ Architecture

<div align="center">
<img src="docs/images/architecture.png" alt="CodeZero Architecture" width="85%"/>
</div>

<br/>

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        PATIENT  ←──  Mobile / Desktop Browser           │
│                                                                          │
│   patient_app.html  ──────────────────────────▶  FastAPI Server          │
│   (standalone HTML,                              hospital_server.py      │
│    no build step)                                localhost:8001           │
│                                                        │                 │
│   ┌────────────────────────────────────────────────────┴──────────┐      │
│   │                    Azure AI Services                          │      │
│   │                                                               │      │
│   │  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐  │      │
│   │  │ Azure Speech │  │ Azure OpenAI │  │ Azure AI Search    │  │      │
│   │  │ STT + Auto   │  │ GPT-4 + RAG  │  │ Medical Knowledge  │  │      │
│   │  │ Lang Detect  │  │ Triage Logic │  │ Semantic Ranking   │  │      │
│   │  └─────────────┘  └──────────────┘  └────────────────────┘  │      │
│   │                                                               │      │
│   │  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐  │      │
│   │  │ Azure Trans- │  │ Azure Maps   │  │ Azure Content      │  │      │
│   │  │ lator 100+   │  │ ETA + Route  │  │ Safety (optional)  │  │      │
│   │  │ Languages    │  │ Live Traffic │  │ Input Filtering    │  │      │
│   │  └─────────────┘  └──────────────┘  └────────────────────┘  │      │
│   └──────────────────────────────────────────────────────────────┘      │
│                                                                          │
│                        Hospital Queue (SQLite)                           │
│                              │                                           │
│                              ▼                                           │
│   hospital_dashboard.html  ◀──  ER Staff View                           │
│   (standalone HTML)             KPIs · Patient Cards · Countdown         │
│                                 Live Map · Medical History               │
└──────────────────────────────────────────────────────────────────────────┘
```

<br/>

## ☁️ Azure Services

| Service | What It Does | AI-102 Domain |
|:---|:---|:---:|
| **Azure OpenAI** (GPT-4) | Conversational AI, triage reasoning, dynamic question generation | Generative AI |
| **Azure AI Search** | Medical knowledge base with semantic search for RAG retrieval | Knowledge Mining |
| **Azure AI Document Intelligence** | Extract text from medical PDFs and clinical guidelines | Knowledge Mining |
| **Azure Speech Services** | Voice input with automatic language detection (10 languages) | NLP |
| **Azure Translator** | Real-time translation across 100+ languages | NLP |
| **Azure Maps** | ETA calculation with live traffic, nearest hospital routing | Plan & Manage |
| **Azure Content Safety** | Filter harmful or irrelevant content from patient input | Responsible AI |

> Every Azure service has a **graceful fallback** — the system works fully offline with rule-based triage, keyword search, haversine distance, and a built-in 440-hospital database.

<br/>

## 🗄️ Hospital Database

The system ships with a comprehensive, pre-loaded emergency hospital database — no external API needed for hospital discovery:

| Country | Hospitals | Coverage |
|:---|:---:|:---|
| 🇩🇪 Germany | **232** | All 16 Bundesländer at district level |
| 🇬🇧 United Kingdom | **121** | England, Scotland, Wales, Northern Ireland — major NHS A&E departments |
| 🇹🇷 Turkey | **87** | All major provinces — university, city, and training hospitals |
| **Total** | **440** | |

**Smart ranking formula:**

```python
effective_eta = travel_time_minutes + occupancy_penalty(low=0, medium=+10, high=+25, full=+60)
```

The system evaluates up to **10 candidates** within a 150 km radius and returns the **top 3** sorted by effective ETA — ensuring patients reach the best *available* hospital, not just the nearest one.

<br/>

## 🧪 Demo Mode

CodeZero runs **fully without Azure credentials** in demo mode — perfect for evaluation, development, and showcasing:

| Feature | ☁️ With Azure | 🖥️ Demo Mode |
|:---|:---|:---|
| Triage logic | GPT-4 + RAG | Rule-based keyword engine |
| Translation | Azure Translator (100+ languages) | Passthrough (original text) |
| Voice input | Azure Speech STT | Browser Web Speech API fallback |
| Hospital search | Azure Maps POI | Built-in 440-hospital database |
| ETA calculation | Real-time traffic data | Haversine formula + 55 km/h estimate |
| Knowledge search | Azure AI Search (semantic) | Local file keyword matching |

<br/>

## 🎬 Demo Scenarios

### Scenario 1 — 🚨 Chest Pain → EMERGENCY

```
1. Click "Chest Pain" on the input page
2. Answer: pain radiates to arm, severity 8+, sweating + shortness of breath
3. → EMERGENCY — Suspected Acute Coronary Syndrome
```

### Scenario 2 — 💊 Mild Headache → ROUTINE

```
1. Click "Mild Headache"
2. Answer: started days ago, severity 3/10, no alarming symptoms
3. → ROUTINE — Self-care advised
```

### Scenario 3 — ⚡ Stroke Symptoms → EMERGENCY

```
1. Click "Stroke Symptoms"
2. FAST assessment: sudden onset, facial droop, arm weakness, speech difficulty
3. → EMERGENCY — Possible Stroke (FAST positive)
```

### Scenario 4 — 🇩🇪 Multilingual (German)

```
1. Click "Demo Deutsch"
2. System auto-detects German, continues the entire conversation in Deutsch
3. Questions shown in German; backend processes in English
```

### Scenario 5 — 🇸🇦 RTL Layout (Arabic)

```
1. Click "Demo Arabic"
2. System auto-detects Arabic; entire UI switches to right-to-left layout
3. Demonstrates full RTL language support
```

<br/>

## 🚀 Quick Start

### Prerequisites

- **Python 3.11+**
- Azure subscription *(optional — demo mode works without it)*

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

### 2. Configure Environment *(optional)*

```bash
cp .env.example .env
```

<details>
<summary><b>📋 Required Environment Variables</b> (click to expand)</summary>

```env
# ── Azure OpenAI ──────────────────────────────
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_KEY=your-key
AZURE_OPENAI_API_VERSION=2024-12-01-preview
GPT_DEPLOYMENT=your-gpt4-deployment-name

# ── Azure AI Search ───────────────────────────
SEARCH_ENDPOINT=https://your-search.search.windows.net
SEARCH_KEY=your-key
SEARCH_INDEX_NAME=medical-knowledge-index

# ── Azure Speech ──────────────────────────────
SPEECH_KEY=your-key
SPEECH_REGION=westeurope

# ── Azure Translator ─────────────────────────
TRANSLATOR_KEY=your-key
TRANSLATOR_ENDPOINT=https://api.cognitive.microsofttranslator.com
TRANSLATOR_REGION=global

# ── Azure Maps (optional — haversine fallback) ─
MAPS_SUBSCRIPTION_KEY=your-key

# ── Optional Services ────────────────────────
DOCUMENT_INTELLIGENCE_ENDPOINT=https://your-doc-intel.cognitiveservices.azure.com/
DOCUMENT_INTELLIGENCE_KEY=your-key
CONTENT_SAFETY_ENDPOINT=https://your-content-safety.cognitiveservices.azure.com/
CONTENT_SAFETY_KEY=your-key

# ── Hospital Configuration ───────────────────
HOSPITAL_NAME=City General Hospital
HOSPITAL_LOCATION_LAT=48.7758
HOSPITAL_LOCATION_LON=9.1829
```

> **Note:** `GPT_DEPLOYMENT` must match your **exact deployment name** in Azure OpenAI Studio — not the model name.

</details>

### 3. Index Medical Guidelines *(one-time, optional)*

```bash
python setup_index.py
```

This processes `data/medical_guidelines/*.txt`, chunks the documents, and uploads them to Azure AI Search with semantic configuration. Skipped gracefully if no Azure credentials are set.

### 4. Start the Server

```bash
python hospital_server.py
# → Server running at http://localhost:8001
```

### 5. Open the Apps

| App | URL | Description |
|:---|:---|:---|
| 🧑‍⚕️ Patient App | Open `ui/patient_app.html` in browser | Patient-facing triage interface |
| 🏥 ER Dashboard | `http://localhost:8001` | Hospital staff command center |

> Both HTML files are **fully standalone** — zero build step, no npm, no frameworks. Just open in any modern browser.

<br/>

## 📁 Project Structure

```
CodeZero/
├── 📄 hospital_server.py           # FastAPI REST API — 8+ endpoints
├── 📄 setup_index.py               # One-time: process + upload medical guidelines
├── 📄 requirements.txt
│
├── 📂 src/
│   ├── triage_engine.py            # 🧠 Core AI — GPT-4 + RAG + mock fallback (1,399 lines)
│   ├── maps_handler.py             # 🗺️ 440 hospitals + ETA routing (685 lines)
│   ├── speech_handler.py           # 🎙️ Azure Speech STT + auto language detection
│   ├── translator.py               # 🌍 Azure Translator — multilingual support
│   ├── knowledge_indexer.py        # 📚 Azure AI Search — index + semantic search
│   ├── document_processor.py       # 📄 Azure Doc Intelligence — PDF extraction
│   ├── health_db.py                # 💊 Health records DB — 30 demo patients (DE/TR/UK)
│   ├── hospital_queue.py           # 🏥 SQLite patient queue (GDPR-compliant)
│   └── safety_filter.py            # 🛡️ Azure Content Safety (optional)
│
├── 📂 ui/
│   ├── patient_app.html            # 📱 Standalone patient triage app
│   └── hospital_dashboard.html     # 📊 Standalone ER command center
│
├── 📂 data/
│   └── medical_guidelines/         # 📋 6 clinical protocols (chest pain, stroke, ...)
│
└── 📂 tests/
    ├── test_scenarios.py           # 🧪 Automated clinical test scenarios
    └── test_integration.py         # 🔗 Integration tests
```

<br/>

## 🩺 Health Records Database

The demo includes **30 richly detailed patient records** (10 per country) with full medical histories:

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
- Epilepsy, Parkinson disease
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

<br/>

## 🔌 API Endpoints

| Endpoint | Method | Description |
|:---|:---:|:---|
| `/api/transcribe` | `POST` | Audio → text via Azure Speech |
| `/api/questions` | `POST` | Generate triage follow-up questions |
| `/api/assess` | `POST` | Full triage assessment with pre-arrival advice |
| `/api/hospitals` | `POST` | Find nearest hospitals with ETA |
| `/api/submit` | `POST` | Submit patient to hospital queue |
| `/api/patients` | `GET` | List incoming patients (dashboard) |
| `/api/stats` | `GET` | Queue KPIs and statistics |
| `/api/patients/{id}` | `GET` | Single patient full detail |

<br/>

## 💰 Cost Estimates

<details>
<summary><b>Azure API pricing breakdown</b> (click to expand)</summary>

| Service | Unit | Estimated Cost |
|:---|:---|---:|
| Azure OpenAI GPT-4 (input) | per 1K tokens | ~$0.03 |
| Azure OpenAI GPT-4 (output) | per 1K tokens | ~$0.06 |
| Typical triage session | ~2,000 tokens | ~$0.09/patient |
| Azure AI Search | per 1K queries | ~$0.005 |
| Azure Translator | per 1M characters | ~$10.00 |
| Azure Speech STT | per audio hour | ~$1.00 |
| Azure Maps Route | per 1K requests | ~$0.50 |

**Estimated monthly cost @ 100 patients/day: ~$300/month**

</details>

<br/>

## 🏛️ Design Principles

| Principle | How It's Implemented |
|:---|:---|
| **⚡ Speed** | < 5 sec per interaction; 440-hospital DB for instant lookup; cached translations |
| **🎯 Simplicity** | Max 5 questions; 54px touch targets; clean minimal UI |
| **🔬 Trust** | Every assessment cites medical guideline sources; RAG-grounded responses |
| **🔒 Privacy** | GDPR-compliant: GPS rounded to ~1 km; no PII stored; anonymous patient IDs |
| **📱 Mobile-First** | Centered 720px layout; large buttons; voice input support |
| **🌍 Multilingual** | 10 languages auto-detected; full RTL layout for Arabic/Hebrew/Farsi |
| **🛡️ Resilience** | Every Azure service has a fallback; app never crashes on missing credentials |
| **📦 Portability** | HTML files are 100% standalone — open directly in any browser, no build step |

<br/>

---

<div align="center">

**Built with ❤️ using Azure AI Services**

<sub>This project demonstrates the integration of 7 Azure AI services for a real-world healthcare scenario.</sub>

<br/>

[⬆ Back to Top](#-codezero)

</div>
