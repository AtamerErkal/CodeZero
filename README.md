# 🏥 Intelligent Pre-Hospital Triage System

An AI-powered pre-hospital emergency triage web application that enables patients to receive intelligent triage assessment **before** arriving at the hospital. The system provides real-time hospital notification, multilingual voice input, and ETA calculation.

## Core Innovation

Unlike existing symptom checkers, this system features:

1. **Proactive Hospital Notification** — Hospital ER receives patient data + ETA before arrival
2. **Voice-First + Auto Language Detection** — Patient speaks in ANY language; AI auto-detects and continues in that language
3. **Dynamic Interactive Questioning** — AI-generated follow-up questions grounded in medical guidelines via RAG
4. **Real-Time Routing** — Azure Maps integration for ETA calculation with traffic awareness
5. **ER Preparation Dashboard** — Hospital staff see incoming patients with countdown timers

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                    PATIENT (Mobile/Web)                           │
│  Voice/Text Input → Language Detection → Dynamic Questions → ETA │
└───────────────────────────────┬──────────────────────────────────┘
                                │
                    ┌───────────▼───────────┐
                    │    STREAMLIT APP       │
                    │  (patient_app.py)      │
                    └───────────┬───────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
┌───────▼───────┐   ┌──────────▼──────────┐   ┌───────▼───────┐
│ Azure Speech  │   │   Azure OpenAI      │   │  Azure Maps   │
│ (STT + Lang   │   │   (GPT-4 + RAG)     │   │  (ETA + Route)│
│  Detection)   │   │                     │   │               │
└───────────────┘   └──────────┬──────────┘   └───────────────┘
                               │
                    ┌──────────▼──────────┐
                    │  Azure AI Search    │
                    │  (Medical KB Index) │
                    │  + Doc Intelligence │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  Azure Translator   │
                    │  (100+ Languages)   │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  Hospital Queue     │
                    │  (SQLite DB)        │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  ER DASHBOARD       │
                    │ (hospital_dashboard │
                    │      .py)           │
                    └─────────────────────┘
```

## Azure Services Used (AI-102 Aligned)

| Service | Purpose | AI-102 Domain |
|---------|---------|---------------|
| Azure OpenAI (GPT-4) | Conversational AI, triage reasoning, question generation | Generative AI |
| Azure AI Search | Medical knowledge base indexing, semantic search | Knowledge Mining |
| Azure AI Document Intelligence | Extract text from medical PDFs/guidelines | Knowledge Mining |
| Azure Speech Services | Voice input with auto language detection | NLP |
| Azure Translator | Multilingual support (100+ languages) | NLP |
| Azure Maps | ETA calculation, hospital routing | Plan & Manage |
| Azure Content Safety | Filter harmful content (optional) | Responsible AI |

## Project Structure

```
medical-triage-ai/
├── .env                          # Azure credentials
├── .gitignore
├── README.md
├── requirements.txt
├── setup_index.py                # One-time indexing setup script
├── data/
│   └── medical_guidelines/       # Medical protocol documents
│       ├── chest_pain_protocol.txt
│       ├── stroke_protocol.txt
│       ├── diabetic_emergency.txt
│       ├── trauma_protocol.txt
│       └── respiratory_emergency.txt
├── src/
│   ├── __init__.py
│   ├── document_processor.py     # Azure Document Intelligence
│   ├── knowledge_indexer.py      # Azure AI Search indexing + local fallback
│   ├── speech_handler.py         # Azure Speech (STT + language detection)
│   ├── translator.py             # Azure Translator
│   ├── triage_engine.py          # Core AI triage logic (OpenAI + RAG)
│   ├── maps_handler.py           # Azure Maps (ETA calculation)
│   ├── safety_filter.py          # Azure Content Safety (optional)
│   └── hospital_queue.py         # Patient queue management (SQLite)
├── ui/
│   ├── patient_app.py            # Streamlit patient-facing app (voice + text)
│   └── hospital_dashboard.py     # Streamlit ER staff dashboard (auto-refresh)
└── tests/
    ├── __init__.py
    └── test_scenarios.py         # Automated test suite (22 tests)
```

## Setup Instructions

### Prerequisites

- Python 3.11+
- Azure subscription with the following services provisioned:
  - Azure OpenAI (GPT-4 deployment)
  - Azure AI Search
  - Azure AI Document Intelligence
  - Azure Speech Services
  - Azure Translator
  - Azure Maps
  - Azure Content Safety (optional)

### 1. Clone and Install

```bash
cd medical-triage-ai
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows
pip install -r requirements.txt
```

### 2. Configure Environment

Edit `.env` with your Azure credentials:

```bash
# Required
AZURE_OPENAI_ENDPOINT=https://your-openai.openai.azure.com/
AZURE_OPENAI_KEY=your-key
GPT_DEPLOYMENT=your-gpt4-deployment-name

SEARCH_ENDPOINT=https://your-search.search.windows.net
SEARCH_KEY=your-key

SPEECH_KEY=your-key
SPEECH_REGION=westeurope

TRANSLATOR_KEY=your-key

MAPS_SUBSCRIPTION_KEY=your-key

# Optional
DOCUMENT_INTELLIGENCE_ENDPOINT=...
CONTENT_SAFETY_ENDPOINT=...
```

### 3. Index Medical Guidelines

Run the setup script to process and index medical guidelines:

```bash
python setup_index.py
```

This will:
1. Read all guideline files from `data/medical_guidelines/`
2. Extract and chunk text content
3. Create the Azure AI Search index with semantic configuration
4. Upload all chunks to the index

> **Note:** Without Azure AI Search credentials, the system falls back to local keyword-based search over the guideline text files. The setup script will warn but the app will still function.

### 4. Run the Patient App

```bash
streamlit run ui/patient_app.py
```

### 5. Run the Hospital Dashboard

```bash
streamlit run ui/hospital_dashboard.py -- --server.port 8502
```

### 6. Run Tests

```bash
python -m pytest tests/test_scenarios.py -v
```

## Demo Usage Guide

The system works in **demo mode** without any Azure credentials. In demo mode:

- Translation passes through text unchanged
- Triage uses keyword-based mock assessment
- ETA uses straight-line distance estimation
- Knowledge search uses local file matching

### Demo Scenarios

1. **Chest Pain → Emergency:**
   Click "💔 Chest Pain" → Answer questions → Get EMERGENCY triage

2. **Mild Headache → Routine:**
   Click "🤕 Headache" → Answer questions → Get ROUTINE triage

3. **Stroke Symptoms → Emergency:**
   Click "🧠 Stroke" → Answer questions → Get EMERGENCY triage

4. **German Input:**
   Click "🇩🇪 Demo (German)" → System detects German → Continues in German

### Hospital Dashboard

Open the dashboard at port 8502 to see incoming patients. Use the Admin tab to add test patients and observe the real-time queue management.

## Patient Journey

```
1. Patient opens app → types or speaks symptoms
2. System auto-detects language (e.g., German)
3. AI generates 3-5 targeted follow-up questions
4. Patient answers questions (translated to their language)
5. AI performs RAG-grounded triage assessment
6. Patient shares location → ETA calculated
7. Hospital receives notification with countdown timer
8. ER staff prepare for patient arrival
```

## Key Technical Highlights

### RAG Pipeline
Medical guidelines are chunked, indexed in Azure AI Search, and retrieved as context for GPT-4. This ensures triage decisions are grounded in clinical protocols rather than hallucinated.

### Agentic AI
The system dynamically decides which questions to ask based on the patient's initial complaint and previous answers. This multi-step reasoning adapts the assessment path in real-time.

### Multilingual Support
Azure Speech auto-detects from 10 candidate languages. Azure Translator handles backend translation so all AI reasoning happens in English while the patient interacts in their native language.

### Graceful Degradation
Every Azure service has a fallback mode. The system remains functional (with reduced capability) even if individual services are unavailable.

## Disclaimer

⚠️ **This is a demonstration system for educational purposes.** It is NOT a certified medical device and should NOT be used for real medical triage decisions. Always call emergency services (112/911) for genuine medical emergencies.

## License

Educational project
