"""
Triage Engine Module
====================
Core AI-powered triage logic. Combines Azure OpenAI (GPT-5.2) with RAG
from the medical knowledge base to perform dynamic patient assessment
and triage classification.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# Triage level constants
TRIAGE_EMERGENCY = "EMERGENCY"
TRIAGE_URGENT = "URGENT"
TRIAGE_ROUTINE = "ROUTINE"

TRIAGE_COLORS = {
    TRIAGE_EMERGENCY: "🔴",
    TRIAGE_URGENT: "🟠",
    TRIAGE_ROUTINE: "🟢",
}

TRIAGE_DESCRIPTIONS = {
    TRIAGE_EMERGENCY: "Immediate medical attention required",
    TRIAGE_URGENT: "Needs medical attention soon",
    TRIAGE_ROUTINE: "Non-urgent, can wait or self-care",
}

# ---------------------------------------------------------------------------
# Demographic intake questions — always asked first before AI clinical questions.
# Answers are injected into the GPT-5.2 prompt so the model can adapt questions
# to the patient's risk profile (e.g. cardiac risk is higher for males over 45).
# ---------------------------------------------------------------------------
DEMOGRAPHIC_QUESTIONS: list[dict] = [
    {
        "question": "What is your age range?",
        "type": "multiple_choice",
        "options": ["Under 12", "12-17", "18-29", "30-44", "45-59", "60-74", "75+"],
        "clinical_rationale": "Age significantly affects risk stratification for most conditions",
        "is_demographic": True,
    },
    {
        "question": "What is your biological sex?",
        "type": "multiple_choice",
        "options": ["Male", "Female", "Prefer not to say"],
        "clinical_rationale": "Biological sex affects symptom presentation and risk profiles",
        "is_demographic": True,
    },
]


# ---------------------------------------------------------------------------
# OR-question post-processor
# ---------------------------------------------------------------------------
# When the AI generates a yes_no question that asks about two conditions
# connected by "or" (e.g. "Do you have chest pain or shortness of breath?"),
# the answer "Yes" is clinically meaningless — yes to which condition?
# This function detects that pattern and converts the question to
# multiple_choice so the patient can select exactly what applies.
#
# Applied to every question returned by generate_next_question() as a
# second line of defence — the system prompt already forbids the pattern,
# but AI models sometimes ignore instructions.

import re as _re

# Common English question prefixes that precede the actual symptom/condition description.
# These are stripped from the left half of an OR split so we get the bare symptom label.
_Q_PREFIX_RE = _re.compile(
    r"^(?:"
    r"do you (?:also |currently |still |now )?(?:have|feel|notice|experience|suffer from|get)|"
    r"are you (?:also |currently |still |now )?(?:experiencing|having|feeling|noticing)|"
    r"have you (?:also |been )?(?:experiencing|having|noticing|had)|"
    r"is (?:the |your |there (?:any |also )?)?\w+(?:\s+\w+)? |"  # "is the discharge", "is your pain"
    r"does (?:the |your )?\w+(?:\s+\w+)? "                       # "does the wound"
    r")\s*",
    _re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Drug & condition risk maps — deterministic clinical enrichment.
# Applied before any LLM call so interpretation is code-guaranteed, not prompt-hoped.
# ---------------------------------------------------------------------------
_DRUG_RISK_MAP: dict[str, list[str]] = {
    # alpha-1 blockers
    "tamsulosin":   ["orthostatic hypotension", "first-dose syncope", "IFIS risk during eye surgery"],
    "doxazosin":    ["orthostatic hypotension", "syncope on standing"],
    "alfuzosin":    ["orthostatic hypotension", "syncope on standing"],
    # anticoagulants — any trauma/head/abdominal pain threshold drops
    "warfarin":     ["major bleeding risk", "INR-dependent", "intracranial haemorrhage on minor head trauma"],
    "apixaban":     ["major GI/intracranial bleeding", "occult bleeding on minor trauma"],
    "rivaroxaban":  ["major GI/intracranial bleeding", "occult bleeding on minor trauma"],
    "dabigatran":   ["GI bleeding", "intracranial bleeding risk"],
    "edoxaban":     ["GI bleeding", "intracranial bleeding risk"],
    "clopidogrel":  ["bleeding risk amplified with aspirin", "GI bleeding"],
    "ticagrelor":   ["bleeding risk", "dyspnoea side-effect"],
    "aspirin":      ["GI bleeding risk", "antiplatelet effect"],
    "heparin":      ["HIT risk", "major bleeding"],
    # beta-blockers — mask tachycardia, blunt compensatory HR
    "metoprolol":   ["masks tachycardia in shock/sepsis", "blunts compensatory HR", "bradycardia risk"],
    "bisoprolol":   ["masks tachycardia in shock/sepsis", "blunts compensatory HR"],
    "atenolol":     ["masks tachycardia in shock/sepsis", "blunts compensatory HR"],
    "carvedilol":   ["masks tachycardia", "orthostatic hypotension"],
    "propranolol":  ["masks tachycardia", "bronchospasm risk in asthma"],
    # ACE-I / ARB
    "lisinopril":   ["angioedema risk", "hyperkalaemia", "AKI in dehydration/NSAID co-use"],
    "enalapril":    ["angioedema risk", "hyperkalaemia"],
    "ramipril":     ["angioedema risk", "hyperkalaemia"],
    "losartan":     ["hyperkalaemia", "AKI in dehydration"],
    "valsartan":    ["hyperkalaemia", "AKI in dehydration"],
    "candesartan":  ["hyperkalaemia", "AKI in dehydration"],
    # diuretics
    "furosemide":   ["hypokalaemia", "dehydration/orthostasis", "prerenal AKI"],
    "spironolactone": ["hyperkalaemia", "gynaecomastia"],
    "hydrochlorothiazide": ["hypokalaemia", "hyponatraemia", "dehydration"],
    # statins
    "atorvastatin": ["myopathy/rhabdomyolysis risk (rare but critical in muscle pain)"],
    "simvastatin":  ["myopathy/rhabdomyolysis risk"],
    # diabetes drugs
    "metformin":    ["lactic acidosis in AKI/sepsis/contrast exposure"],
    "insulin":      ["hypoglycaemia presenting as confusion/seizure/syncope"],
    "glipizide":    ["hypoglycaemia"],
    "glyburide":    ["prolonged hypoglycaemia risk"],
    "sitagliptin":  ["pancreatitis association"],
    # immunosuppression / steroids
    "prednisolone": ["masked infection signs", "adrenal crisis if dose missed", "GI ulcer", "AVN"],
    "prednisone":   ["masked infection signs", "adrenal crisis if dose missed", "GI ulcer"],
    "dexamethasone":["masked infection/fever", "hyperglycaemia"],
    "methotrexate": ["pancytopenia ->atypical infection", "hepatotoxicity"],
    "azathioprine": ["immunosuppression ->atypical infection presentation"],
    "ciclosporin":  ["nephrotoxicity", "hypertension", "drug interactions"],
    "tacrolimus":   ["nephrotoxicity", "neurotoxicity", "PTLD"],
    # psychiatric
    "lithium":      ["lithium toxicity in dehydration/AKI — narrow therapeutic index"],
    "clozapine":    ["agranulocytosis ->sepsis risk", "QTc prolongation", "myocarditis"],
    "haloperidol":  ["QTc prolongation", "NMS risk"],
    "quetiapine":   ["QTc prolongation", "orthostatic hypotension"],
    "olanzapine":   ["metabolic syndrome", "QTc prolongation"],
    "amitriptyline":["QTc prolongation", "anticholinergic toxicity in overdose"],
    "sertraline":   ["SSRI + NSAID ->GI bleeding", "serotonin syndrome risk"],
    "fluoxetine":   ["SSRI + NSAID ->GI bleeding", "serotonin syndrome risk", "long half-life"],
    # cardiac / anti-arrhythmic
    "digoxin":      ["digoxin toxicity in dehydration/AKI/hypokalaemia — narrow therapeutic index"],
    "amiodarone":   ["thyroid toxicity", "pulmonary toxicity", "photosensitivity", "QTc prolongation"],
    "diltiazem":    ["bradycardia + AV block risk", "negative inotropy"],
    "verapamil":    ["bradycardia + AV block risk", "negative inotropy", "constipation"],
    # antibiotics
    "ciprofloxacin":["tendon rupture risk", "QTc prolongation", "C.diff risk"],
    "levofloxacin": ["tendon rupture risk", "QTc prolongation", "C.diff risk"],
    "azithromycin": ["QTc prolongation"],
    # NSAIDs
    "ibuprofen":    ["GI bleeding", "AKI in dehydration", "worsens heart failure"],
    "naproxen":     ["GI bleeding", "AKI in dehydration", "worsens heart failure"],
    "diclofenac":   ["GI bleeding", "AKI in dehydration", "cardiac risk"],
    # opioids
    "morphine":     ["respiratory depression", "constipation ->obstruction"],
    "oxycodone":    ["respiratory depression", "constipation"],
    "codeine":      ["variable metabolism — ultra-rapid metaboliser toxicity risk"],
    "tramadol":     ["serotonin syndrome with SSRIs", "seizure threshold lowering"],
    # hormonal
    "ocp":          ["VTE/PE risk — especially smoker ≥35", "hypertension"],
    "combined oral contraceptive": ["VTE/PE risk", "hypertension"],
    "hrt":          ["VTE/PE risk", "breast cancer association"],
    "testosterone": ["polycythaemia", "VTE risk"],
    # prostate-specific
    "bicalutamide": ["hepatotoxicity", "hot flushes", "DVT risk"],
    "leuprolide":   ["osteoporosis", "metabolic syndrome", "DVT risk"],
}

_CONDITION_RISK_MAP: dict[str, list[str]] = {
    "atrial fibrillation":           ["embolic stroke", "embolic mesenteric ischaemia", "rate-dependent acute CHF"],
    "heart failure":                 ["acute decompensation on fluid/salt load", "low cardiac reserve", "arrhythmia"],
    "previous mi":                   ["lower threshold for ACS work-up — recurrence risk × 3"],
    "coronary artery disease":       ["ACS — lower symptom threshold", "stent thrombosis"],
    "hypertension":                  ["aortic dissection risk", "hypertensive emergency", "stroke risk"],
    "diabetes":                      ["silent MI", "DKA/HHS", "atypical infection presentation", "DAN — atypical pain"],
    "diabetes mellitus":             ["silent MI", "DKA/HHS", "atypical infection presentation"],
    "copd":                          ["CO2 retention on high-flow O2", "right heart strain", "spontaneous pneumothorax"],
    "asthma":                        ["status asthmaticus", "NSAID-sensitive subtype", "steroid-dependent"],
    "ckd":                           ["hyperkalaemia", "contrast nephropathy risk", "altered drug clearance", "fluid overload"],
    "chronic kidney disease":        ["hyperkalaemia", "contrast nephropathy risk", "altered drug clearance"],
    "liver cirrhosis":               ["variceal bleeding", "hepatic encephalopathy", "spontaneous bacterial peritonitis"],
    "previous dvt":                  ["DVT recurrence risk ~10× baseline", "PE risk elevated"],
    "previous pe":                   ["PE recurrence risk elevated", "chronic thromboembolic disease"],
    "malignancy":                    ["hypercoagulable state", "bone metastasis ->cord compression/fracture", "infection in neutropenia"],
    "cancer":                        ["hypercoagulable state", "bone metastasis ->cord compression/fracture", "infection in neutropenia"],
    "prostate cancer":               ["mild hypercoagulable state", "bone metastasis ->pathological fracture/cord compression", "spinal cord compression risk"],
    "post-prostatectomy":            ["VTE/PE risk elevated", "lymphoedema", "urinary baseline altered"],
    "prostatectomy":                 ["VTE/PE risk elevated", "urinary baseline altered"],
    "stroke":                        ["recurrent stroke/TIA", "dysphagia ->aspiration risk", "reduced mobility ->DVT"],
    "previous stroke":               ["recurrent stroke/TIA — lower NIHSS threshold for imaging"],
    "epilepsy":                      ["post-ictal state mimics other conditions", "SUDEP risk with poor control"],
    "immunocompromised":             ["atypical infection presentation", "opportunistic pathogens", "fever may be absent"],
    "hiv":                           ["opportunistic infection", "immune reconstitution", "drug interactions with ART"],
    "sickle cell":                   ["vaso-occlusive crisis", "acute chest syndrome", "splenic sequestration", "stroke"],
    "sickle cell disease":           ["vaso-occlusive crisis", "acute chest syndrome — life-threatening"],
    "pregnancy":                     ["ectopic pregnancy if early", "pre-eclampsia/eclampsia if 20+ weeks", "PE risk elevated"],
    "aaa":                           ["rupture — immediately life-threatening", "endoleak post-repair"],
    "abdominal aortic aneurysm":     ["rupture — immediately life-threatening"],
    "aortic stenosis":               ["syncope = severe ->high mortality", "heart failure", "sudden cardiac death"],
    "osteoporosis":                  ["fragility fracture on minimal trauma", "vertebral compression fracture"],
    "parkinsons":                    ["orthostatic hypotension", "aspiration risk", "falls risk"],
    "dementia":                      ["atypical presentation of all conditions", "pain reporting unreliable"],
    "myasthenia gravis":             ["myasthenic crisis with infections/certain drugs", "respiratory compromise"],
}


def _fix_or_question(q: dict, lang_base: str = "en") -> None:
    """Convert a malformed yes_no question that contains multiple findings into
    multiple_choice in-place, so each finding becomes a selectable option.

    Always operates on question_en (always English) — question may be German.
    Uses language-appropriate labels for "Both" and "Neither".

    Handles two patterns:
      • 2-finding OR question  ->["Finding A", "Finding B", <both>, <neither>]
      • 3+ findings (commas+or) ->["Finding A", "Finding B", "Finding C", <none>]
    """
    if not q or q.get("type") != "yes_no":
        return

    # For non-English: don't generate option labels from English question fragments.
    # _validate_question detects OR in question_en and forces an LLM retry that
    # will produce correct Turkish/German options directly.
    if lang_base not in ("en", "tr", ""):
        return

    # Language-specific aggregate labels
    _both    = {"de": "Beides",           "tr": "Her ikisi"}.get(lang_base, "Both")
    _neither = {"de": "Keines von beiden", "tr": "Hiçbiri"  }.get(lang_base, "Neither of these")
    _none    = {"de": "Keines davon",      "tr": "Hiçbiri"  }.get(lang_base, "None of these")

    # Use question_en for English regex matching; question may be German
    text_en = (q.get("question_en") or q.get("question", "")).strip()

    has_comma = "," in text_en
    has_or    = bool(_re.search(r"\bor\b", text_en, _re.IGNORECASE))

    _connector_prefix = _re.compile(r"^\s*(?:or|and)\s+", _re.IGNORECASE)

    def _clean_fragment(raw: str) -> str:
        raw = _connector_prefix.sub("", raw)
        raw = _Q_PREFIX_RE.sub("", raw).strip().rstrip("?,;.").strip()
        words = raw.split()
        if len(words) > 4:
            raw = " ".join(words[:4])
        return (raw[0].upper() + raw[1:]) if raw else ""

    # ── Pattern 1: commas AND/OR connectors ->3+ findings ────────────────────
    if has_comma and has_or:
        raw_parts = _re.split(r"\s*,\s*|\s+or\s+", text_en, flags=_re.IGNORECASE)
        fragments = [_clean_fragment(p) for p in raw_parts]
        fragments = [f for f in fragments if len(f) >= 2]

        if len(fragments) >= 3:
            q["type"]    = "multiple_choice"
            q["options"] = fragments + [_none]
            logger.info(
                "_fix_or_question: 3+ findings yes_no ->multiple_choice | options=%s",
                q["options"],
            )
            return

    # ── Pattern 2: simple 2-finding OR question ───────────────────────────────
    if not has_or:
        return

    parts = _re.split(r"\s+or\s+", text_en, maxsplit=1, flags=_re.IGNORECASE)
    if len(parts) != 2:
        return

    opt_a = _clean_fragment(parts[0])
    opt_b = _clean_fragment(parts[1])

    if len(opt_a) < 2 or len(opt_b) < 2:
        return

    q["type"]    = "multiple_choice"
    q["options"] = [opt_a, opt_b, _both, _neither]
    logger.info(
        "_fix_or_question: 2-finding yes_no ->multiple_choice | options=%s",
        q["options"],
    )


def _normalize_options(q: dict, lang_base: str = "en") -> None:
    """Post-process question options in-place after LLM generation.

    1. yes_no: enforce exact standard forms per language — no informal variants.
    2. multiple_choice: remove options that are question fragments (end with '?')
       or are excessively long sentences (> 8 words), which indicate the LLM
       used question text as option labels instead of clean answer choices.
    """
    if not q:
        return

    qtype   = q.get("type", "")
    options = q.get("options") or []

    if qtype == "yes_no":
        _yn: dict[str, list[str]] = {
            "de": ["Ja", "Nein"],
        }
        q["options"] = _yn.get(lang_base, ["Yes", "No"])
        return

    if qtype == "multiple_choice" and options:
        cleaned: list[str] = []
        for opt in options:
            s = str(opt).strip()
            if s.endswith("?"):          # question fragment
                continue
            if len(s.split()) > 8:       # sentence, not a label
                # Truncate to first 6 words rather than drop entirely
                s = " ".join(s.split()[:6])
            if s:
                cleaned.append(s)
        if len(cleaned) >= 2:
            q["options"] = cleaned


def _fix_or_yes_no(result: dict, lang_base: str = "en") -> None:
    """Wrapper for generate_next_question() result format: {done, question}."""
    q = result.get("question")
    if q:
        _fix_or_question(q, lang_base)


class TriageEngine:
    """AI-powered medical triage engine with RAG grounding.

    Uses Azure OpenAI for conversational AI and Azure AI Search
    (via KnowledgeIndexer) for retrieval-augmented generation. The
    engine dynamically generates follow-up questions, analyzes patient
    responses, and produces a grounded triage assessment.

    Attributes:
        openai_client: Azure OpenAI client instance.
        deployment: GPT model deployment name.
        knowledge_indexer: KnowledgeIndexer for RAG search.
        translator: Translator for multilingual support.
    """

    def __init__(
        self,
        knowledge_indexer=None,
        translator=None,
    ) -> None:
        """Initialize the Triage Engine.

        Args:
            knowledge_indexer: Optional KnowledgeIndexer instance.
            translator: Optional Translator instance.
        """
        self.openai_client = None
        self.deployment: str = os.getenv("GPT_DEPLOYMENT", "gpt-4")
        self.knowledge_indexer = knowledge_indexer
        self.translator = translator
        self._initialized = False
        self._init_error: str = ""
        self._hypothesis_cache: dict = {}
        self._init_openai()

    def _init_openai(self) -> None:
        """Initialize Azure OpenAI client.

        AI-102: AzureOpenAI client uses azure_endpoint + api_key for
        authentication. The api_version must match the deployment.
        """
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
        key = os.getenv("AZURE_OPENAI_KEY", "")
        api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")

        if not endpoint or not key or key == "your-key":
            logger.info("Azure OpenAI credentials not configured. Checking for standard OpenAI key...")
            openai_key = os.getenv("OPENAI_API_KEY", "")
            if openai_key and openai_key != "your-key":
                try:
                    from openai import OpenAI
                    self.openai_client = OpenAI(api_key=openai_key)
                    self._initialized = True
                    self.deployment = os.getenv("OPENAI_MODEL", "gpt-4o") # Default to 4o for standard OpenAI
                    logger.info("Standard OpenAI client initialized (model=%s).", self.deployment)
                except Exception as exc:
                    logger.error("Failed to init standard OpenAI client: %s", exc)
            else:
                logger.warning("No AI credentials found. Using mock triage engine.")
            return

        try:
            from openai import AzureOpenAI

            try:
                self.openai_client = AzureOpenAI(
                    azure_endpoint=endpoint,
                    api_key=key,
                    api_version=api_version,
                )
            except TypeError:
                import httpx
                self.openai_client = AzureOpenAI(
                    azure_endpoint=endpoint,
                    api_key=key,
                    api_version=api_version,
                    http_client=httpx.Client(),
                )

            # Validate the deployment with a minimal test call.
            # Uses max_completion_tokens (required by newer models like gpt-5.x).
            # This catches wrong deployment names and auth errors at startup
            # instead of silently falling back to mock on every patient call.
            try:
                self.openai_client.chat.completions.create(
                    model=self.deployment,
                    messages=[{"role": "user", "content": "ping"}],
                    max_completion_tokens=1,
                )
                self._initialized = True
                logger.info(
                    "Azure OpenAI client initialized — deployment '%s' verified OK.",
                    self.deployment,
                )
            except Exception as test_exc:
                err = str(test_exc)
                err_lower = err.lower()
                if "DeploymentNotFound" in err or ("404" in err and "deployment" in err_lower):
                    logger.error(
                        "Azure OpenAI deployment '%s' NOT FOUND. Check GPT_DEPLOYMENT in .env. Error: %s",
                        self.deployment, test_exc,
                    )
                    self._initialized = False
                    self._init_error = f"Deployment '{self.deployment}' not found. Check GPT_DEPLOYMENT in .env."
                elif "401" in err or "unauthorized" in err_lower or "authentication" in err_lower:
                    logger.error("Azure OpenAI auth failed. Check AZURE_OPENAI_KEY. Error: %s", test_exc)
                    self._initialized = False
                    self._init_error = "Authentication failed. Check AZURE_OPENAI_KEY in .env."
                else:
                    # Any other error (network, transient) — mark initialized and retry at call time
                    self._initialized = True
                    logger.warning(
                        "Deployment test call non-fatal error for '%s' (will retry at call time): %s",
                        self.deployment, test_exc,
                    )
        except Exception as exc:
            logger.error("Failed to init Azure OpenAI client: %s", exc)


    def _chat_complete(self, messages: list, max_tokens: int = 800, system_override: str = "") -> str:
        """Wrapper around chat.completions.create that handles model compatibility.

        - Tries response_format=json_object first (standard).
        - Falls back to plain completion if the model does not support it (e.g. gpt-5.x).
        - Always returns the raw string content from the first choice.
        """
        kwargs = dict(
            model=self.deployment,
            messages=messages,
            max_completion_tokens=max_tokens,
        )
        try:
            kwargs["response_format"] = {"type": "json_object"}
            resp = self.openai_client.chat.completions.create(**kwargs)
        except Exception as exc:
            err = str(exc).lower()
            if "response_format" in err or "unsupported" in err or "invalid" in err:
                logger.warning("response_format not supported by deployment '%s', retrying without: %s", self.deployment, exc)
                kwargs.pop("response_format", None)
                resp = self.openai_client.chat.completions.create(**kwargs)
            else:
                raise
        finish = resp.choices[0].finish_reason if resp.choices else None
        content = resp.choices[0].message.content if resp.choices else None
        if finish == "content_filter":
            logger.error("_chat_complete: output filtered by content policy (model=%s)", self.deployment)
            return ""
        if finish == "length":
            logger.warning("_chat_complete: response truncated (finish_reason=length, model=%s) — increase max_tokens", self.deployment)
        if not content:
            logger.error("_chat_complete: empty response (finish_reason=%s, model=%s)", finish, self.deployment)
            return ""
        return content

    # ------------------------------------------------------------------
    # RAG: Retrieve context from knowledge base
    # ------------------------------------------------------------------

    # Medical synonym expansion for better retrieval recall
    _COMPLAINT_SYNONYMS: dict[str, list[str]] = {
        "chest pain": ["chest pain", "angina", "ACS", "STEMI", "myocardial"],
        "heart attack": ["chest pain", "myocardial infarction", "ACS", "cardiac"],
        "shortness of breath": ["dyspnea", "respiratory distress", "breathing difficulty", "SOB"],
        "difficulty breathing": ["dyspnea", "respiratory", "breathing", "airway"],
        "headache": ["headache", "migraine", "cephalgia", "head pain"],
        "stomach pain": ["abdominal pain", "abdomen", "belly pain", "GI"],
        "belly pain": ["abdominal pain", "abdomen", "GI", "gastro"],
        "abdominal pain": ["abdominal pain", "abdomen", "GI", "gastro"],
        "back pain": ["back pain", "lumbar", "spine"],
        "dizzy": ["dizziness", "vertigo", "syncope", "lightheaded"],
        "dizziness": ["dizziness", "vertigo", "syncope", "presyncope"],
        "faint": ["syncope", "loss of consciousness", "LOC", "dizziness"],
        "unconscious": ["cardiac arrest", "syncope", "LOC", "unresponsive"],
        "collapsed": ["cardiac arrest", "syncope", "collapse", "unresponsive"],
        "allergy": ["anaphylaxis", "allergic reaction", "hypersensitivity"],
        "allergic": ["anaphylaxis", "allergic reaction", "hypersensitivity"],
        "bee sting": ["anaphylaxis", "insect sting", "venom", "allergic"],
        "swelling": ["angioedema", "oedema", "swelling"],
        "throat swelling": ["anaphylaxis", "angioedema", "airway"],
        "fever": ["fever", "infection", "sepsis", "pyrexia"],
        "infection": ["sepsis", "infection", "fever", "inflammatory"],
        "confusion": ["altered consciousness", "encephalopathy", "delirium", "sepsis"],
        "seizure": ["seizure", "epilepsy", "convulsion", "status epilepticus"],
        "fit": ["seizure", "epilepsy", "convulsion"],
        "overdose": ["poisoning", "overdose", "toxicology", "intoxication"],
        "poisoning": ["poisoning", "overdose", "toxicology"],
        "stroke": ["stroke", "CVA", "TIA", "cerebrovascular", "facial droop", "weakness"],
        "weakness": ["stroke", "neurological", "paralysis"],
        "arm weakness": ["stroke", "CVA", "neurological"],
        "leg pain": ["fracture", "DVT", "orthopedic", "trauma"],
        "broken bone": ["fracture", "orthopedic", "trauma"],
        "fracture": ["fracture", "orthopedic", "trauma", "bone"],
        "fall": ["trauma", "fracture", "orthopedic", "injury"],
        "injury": ["trauma", "fracture", "orthopedic"],
        "trauma": ["trauma", "fracture", "orthopedic"],
        "diabetes": ["diabetic", "hypoglycaemia", "hyperglycaemia", "glucose"],
        "blood sugar": ["diabetic emergency", "hypoglycaemia", "hyperglycaemia"],
        "low blood sugar": ["hypoglycaemia", "diabetic emergency"],
        "high blood sugar": ["hyperglycaemia", "DKA", "diabetic ketoacidosis"],
        "urine": ["urological", "UTI", "kidney", "renal"],
        "kidney pain": ["renal colic", "urological", "kidney stone"],
        "testicular pain": ["testicular torsion", "urological", "scrotal"],
        "scrotal pain": ["testicular torsion", "urological", "scrotal"],
        "child": ["paediatric", "pediatric", "child", "infant"],
        "baby": ["paediatric", "pediatric", "infant", "neonate"],
        "mental health": ["psychiatric", "mental health", "suicide", "depression"],
        "suicidal": ["psychiatric emergency", "suicide", "mental health crisis"],
        "self harm": ["psychiatric emergency", "self-harm", "mental health"],
        "rash": ["skin", "dermatological", "meningococcal", "allergic"],
        "bleeding": ["haemorrhage", "bleeding", "hemorrhage"],
    }

    def _enhance_query(self, complaint: str) -> str:
        """Expand a chief complaint with clinical synonyms for better RAG recall.

        Maps lay terms to medical terminology so that the search index
        finds relevant protocol documents even when the patient uses
        colloquial language (e.g. "belly pain" ->"abdominal pain GI gastro").

        Args:
            complaint: Raw chief complaint text from the patient.

        Returns:
            Enriched query string combining original terms + medical synonyms.
        """
        complaint_lower = complaint.lower()
        extra_terms: list[str] = []

        for trigger, expansions in self._COMPLAINT_SYNONYMS.items():
            if trigger in complaint_lower:
                extra_terms.extend(expansions)

        if extra_terms:
            # Deduplicate while preserving order
            seen: set[str] = set()
            unique_extra: list[str] = []
            for t in extra_terms:
                if t.lower() not in seen:
                    seen.add(t.lower())
                    unique_extra.append(t)
            enhanced = complaint + " " + " ".join(unique_extra[:12])
            logger.info(
                "RAG query enhanced: '%s' ->'%s'", complaint[:50], enhanced[:100]
            )
            return enhanced

        return complaint

    def _retrieve_context(self, query: str) -> tuple[str, bool, list[str]]:
        """Search the medical knowledge base for relevant guidelines.

        This is the "Retrieval" step of RAG. The search query is enhanced
        with medical synonyms before searching, so lay patient language maps
        to clinical protocol documents. Results are deduplicated, scored,
        and injected into the system prompt as grounding context.

        Returns a 3-tuple (context_text, rag_found, sources) so callers can
        adapt their prompts and surface citations to users.

        Args:
            query: Search query (usually the patient's chief complaint).

        Returns:
            Tuple of (guideline text, rag_found flag, list of source filenames).
            rag_found is True only when at least one result was retrieved.
        """
        if self.knowledge_indexer is None:
            return "", False, []

        try:
            enhanced_query = self._enhance_query(query)
            results = self.knowledge_indexer.search(enhanced_query, top=4)
            if not results:
                logger.info(
                    "RAG: no results for query '%s' — AI will use general knowledge.",
                    query[:60],
                )
                return "", False, []

            context_parts: list[str] = []
            sources: list[str] = []
            for r in results:
                source_name = r.get("source", "Unknown")
                context_parts.append(
                    f"--- Guideline: {r.get('title', source_name)} ---\n"
                    f"{r.get('content', '')}\n"
                )
                # Format source name for display (strip extension, humanise)
                display_name = source_name.replace(".txt", "").replace("_", " ").title()
                if display_name not in sources:
                    sources.append(display_name)

            context_text = "\n".join(context_parts)
            logger.info(
                "RAG: found %d result(s) for query '%s'. Sources: %s",
                len(results), query[:60], sources,
            )
            return context_text, True, sources

        except Exception as exc:
            logger.error("RAG retrieval error: %s", exc)
            return "", False, []

    def _format_medical_history(self, medical_history: Optional[dict]) -> str:
        """Format the full medical record into a concise summary for GPT context."""
        if not medical_history:
            return "None provided."
            
        parts = []
        demo = medical_history.get("patient") or medical_history.get("demographics", {})
        if demo:
            age = demo.get("date_of_birth", "Unknown DOB")
            sex = demo.get("sex", "Unknown Sex")
            parts.append(f"Patient: {demo.get('first_name','')} {demo.get('last_name','')}, {sex}, DOB: {age}")
        
        # Active Conditions
        conds = medical_history.get("diagnoses", [])
        if conds:
            active_conds = [d.get("description", "") for d in conds if d.get("status") == "active"]
            if active_conds:
                parts.append("Active Diagnoses: " + ", ".join(active_conds))
        
        # Medications
        meds = medical_history.get("medications", [])
        if meds:
            active_meds = [f"{m.get('name')} {m.get('dosage')}" for m in meds if m.get("status") == "active"]
            if active_meds:
                parts.append("Current Medications: " + ", ".join(active_meds))
        
        # Allergies
        allergies = medical_history.get("allergies", [])
        if allergies:
            parts.append("Allergies: " + ", ".join([f"{a.get('allergen')} ({a.get('reaction')})" for a in allergies]))

        # Historical baseline vitals — clearly labelled as past values
        vitals = medical_history.get("vitals", [])
        if vitals:
            v = vitals[0]
            recorded = v.get("recorded_at", "date unknown")
            v_str = (
                f"HISTORICAL BASELINE VITALS (recorded {recorded} — NOT the patient's current vitals): "
                f"BP {v.get('bp_systolic','?')}/{v.get('bp_diastolic','?')}, "
                f"HR {v.get('heart_rate','?')}, SpO2 {v.get('spo2','?')}%, Temp {v.get('temperature','?')}°C. "
                f"Use these only as a baseline reference — do NOT assume they reflect the patient's condition today."
            )
            parts.append(v_str)

        # Doctor Notes (Last 2)
        notes = medical_history.get("doctor_notes", [])
        if notes:
            parts.append("Recent Clinical Notes:")
            for n in notes[:2]:
                parts.append(f"- {n.get('note_date')}: {n.get('assessment')} (Plan: {n.get('plan')})")
        
        return "\n".join(parts)

    def _structured_patient_context(
        self,
        medical_history: Optional[dict],
        chief_complaint: str = "",
    ) -> dict:
        """Deterministic code-level clinical enrichment. Converts raw medical history
        into an interpreted risk profile BEFORE any LLM call. All drug/condition
        risks are guaranteed by the code — not hoped-for from a prompt."""
        if not medical_history:
            return {"has_history": False}

        pat = medical_history.get("patient") or medical_history.get("demographics") or {}

        # exact age
        age: Optional[int] = None
        dob = pat.get("date_of_birth")
        if dob:
            try:
                age = datetime.now(timezone.utc).year - int(str(dob)[:4])
            except Exception:
                pass

        # active conditions
        active_conditions = [
            d.get("description", "").strip()
            for d in medical_history.get("diagnoses", [])
            if d.get("status") == "active" and d.get("description")
        ]

        # active medications
        active_meds_raw = [
            {
                "name": (m.get("name") or "").strip(),
                "name_lower": (m.get("name") or "").strip().lower(),
                "dose": m.get("dosage", ""),
                "display": f"{(m.get('name') or '').strip()} {m.get('dosage', '')}".strip(),
            }
            for m in medical_history.get("medications", [])
            if m.get("status") == "active" and m.get("name")
        ]

        # drug-specific risks (deterministic lookup)
        drug_risks: list[dict] = []
        for med in active_meds_raw:
            ml = med["name_lower"]
            for key, risks in _DRUG_RISK_MAP.items():
                if key in ml:
                    drug_risks.append({"drug": med["display"], "risks": risks})
                    break  # one match per drug

        # condition-specific risks
        condition_risks: list[dict] = []
        for cond in active_conditions:
            cl = cond.lower()
            for key, risks in _CONDITION_RISK_MAP.items():
                if key in cl:
                    condition_risks.append({"condition": cond, "risks": risks})
                    break

        # combinatorial red flags — multi-factor interactions
        combo_flags: list[str] = []
        meds_lower = " ".join(m["name_lower"] for m in active_meds_raw)
        conds_lower = " ".join(active_conditions).lower()
        comp_lower  = chief_complaint.lower()

        anticoag_drugs = {"warfarin", "apixaban", "rivaroxaban", "dabigatran", "edoxaban"}
        if any(d in meds_lower for d in anticoag_drugs):
            if any(w in comp_lower for w in ["head", "trauma", "fall", "abdom", "back", "chest"]):
                combo_flags.append(
                    "ANTICOAGULATED PATIENT: even minor-mechanism trauma or pain must be "
                    "treated as potential major bleeding event. Lower imaging threshold significantly."
                )

        alpha1_drugs = {"tamsulosin", "doxazosin", "alfuzosin"}
        if any(d in meds_lower for d in alpha1_drugs):
            if any(w in comp_lower for w in ["dizz", "faint", "syncope", "fall", "lightheaded", "black"]):
                combo_flags.append(
                    "ALPHA-1 BLOCKER + POSTURAL SYMPTOMS: orthostatic hypotension is primary hypothesis. "
                    "Test with lying→standing BP and symptom reproduction before pursuing cardiac/neuro paths."
                )

        if age and age >= 65 and any(d in meds_lower for d in alpha1_drugs):
            combo_flags.append(
                "ELDERLY + ALPHA-BLOCKER: fall risk from orthostasis is high. "
                "Assess for injury from fall AND causative syncope mechanism."
            )

        beta_drugs = {"metoprolol", "bisoprolol", "atenolol", "carvedilol", "propranolol"}
        if any(d in meds_lower for d in beta_drugs):
            if any(w in comp_lower for w in ["sepsis", "infect", "fever", "shock", "pale", "weak"]):
                combo_flags.append(
                    "BETA-BLOCKER: tachycardia is pharmacologically blunted. "
                    "Normal or low HR does NOT exclude shock/sepsis. "
                    "Weight cap-refill, mentation, BP trend more heavily than HR."
                )

        if "diabetes" in conds_lower or "diabetes mellitus" in conds_lower:
            if any(w in comp_lower for w in ["chest", "epigast", "indigest", "jaw", "arm"]):
                combo_flags.append(
                    "DIABETIC PATIENT + CHEST/EPIGASTRIC PAIN: silent MI is common due to "
                    "diabetic autonomic neuropathy. Lower threshold for cardiac work-up even if pain is mild."
                )

        if any(w in conds_lower for w in ["cancer", "carcinoma", "metasta", "lymphoma", "leukaemia"]):
            if any(w in comp_lower for w in ["back", "spine", "leg weak", "bowel", "bladder"]):
                combo_flags.append(
                    "KNOWN MALIGNANCY + BACK/NEURO SYMPTOMS: spinal cord compression / "
                    "pathological fracture must be ruled out. "
                    "Q1: bowel or bladder dysfunction, saddle anaesthesia, bilateral leg weakness."
                )

        if "lithium" in meds_lower:
            combo_flags.append(
                "LITHIUM: narrow therapeutic index — any dehydration, AKI, new medication, "
                "or reduced oral intake can precipitate toxicity (tremor, confusion, GI symptoms)."
            )

        if "digoxin" in meds_lower:
            combo_flags.append(
                "DIGOXIN: narrow therapeutic index — toxicity risk with dehydration, AKI, "
                "hypokalaemia, or drug interactions. GI and visual symptoms may indicate toxicity."
            )

        if age and age >= 75:
            n_meds = len(active_meds_raw)
            if n_meds >= 4:
                combo_flags.append(
                    f"GERIATRIC POLYPHARMACY ({n_meds} active medications): atypical presentations "
                    "are the rule. Screen for delirium, occult infection, drug-drug interactions, "
                    "fall risk. Pain reporting may be unreliable."
                )

        # allergies
        allergies = [
            {"allergen": a.get("allergen"), "reaction": a.get("reaction")}
            for a in medical_history.get("allergies", [])
            if a.get("allergen")
        ]

        # baseline vitals
        baseline_vitals = None
        vitals = medical_history.get("vitals", [])
        if vitals:
            v = vitals[0]
            baseline_vitals = {
                "bp":   f"{v.get('bp_systolic','?')}/{v.get('bp_diastolic','?')}",
                "hr":   v.get("heart_rate"),
                "spo2": v.get("spo2"),
                "temp": v.get("temperature"),
                "date": v.get("recorded_at"),
            }

        # recent doctor notes
        recent_notes = [
            {"date": n.get("note_date"), "assessment": n.get("assessment"), "plan": n.get("plan")}
            for n in (medical_history.get("doctor_notes") or [])[:2]
        ]

        return {
            "has_history":             True,
            "age":                     age,
            "sex":                     pat.get("sex"),
            "name":                    f"{pat.get('first_name','')} {pat.get('last_name','')}".strip(),
            "active_conditions":       active_conditions,
            "active_medications":      [m["display"] for m in active_meds_raw],
            "drug_specific_risks":     drug_risks,
            "condition_specific_risks": condition_risks,
            "combinatorial_red_flags": combo_flags,
            "allergies":               allergies,
            "baseline_vitals":         baseline_vitals,
            "recent_notes":            recent_notes,
            "social_history":          medical_history.get("social_history") or {},
            "family_history":          medical_history.get("family_history") or [],
        }

    def _format_structured_context(self, ctx: dict) -> str:
        """Render a structured patient context dict as a clinical brief for LLM injection.
        Already-interpreted — the LLM reads conclusions, not raw lists."""
        if not ctx.get("has_history"):
            return "No prior medical history on file. Treat as de-novo presentation."

        lines: list[str] = []
        lines.append(
            f"PATIENT: {ctx.get('name') or 'Unknown'} | "
            f"Age {ctx.get('age','?')} | Sex {ctx.get('sex','?')}"
        )

        if ctx["active_conditions"]:
            lines.append("ACTIVE CONDITIONS: " + " | ".join(ctx["active_conditions"]))

        if ctx["condition_specific_risks"]:
            lines.append("CONDITION-DRIVEN CLINICAL RISKS:")
            for r in ctx["condition_specific_risks"]:
                lines.append(f"  • {r['condition']} ->{', '.join(r['risks'])}")

        if ctx["active_medications"]:
            lines.append("CURRENT MEDICATIONS: " + " | ".join(ctx["active_medications"]))

        if ctx["drug_specific_risks"]:
            lines.append("MEDICATION-DRIVEN RISKS (may be the cause or a complicating factor):")
            for r in ctx["drug_specific_risks"]:
                lines.append(f"  • {r['drug']} ->{', '.join(r['risks'])}")

        if ctx["combinatorial_red_flags"]:
            lines.append("⚠ COMBINATORIAL RED FLAGS (multi-factor interactions):")
            for f in ctx["combinatorial_red_flags"]:
                lines.append(f"  ⚠ {f}")

        if ctx["allergies"]:
            lines.append("ALLERGIES: " + " | ".join(
                f"{a['allergen']} ->{a['reaction']}" for a in ctx["allergies"]
            ))

        if ctx["baseline_vitals"]:
            v = ctx["baseline_vitals"]
            lines.append(
                f"BASELINE VITALS ({v['date']}, historical NOT current): "
                f"BP {v['bp']} | HR {v['hr']} | SpO2 {v['spo2']}% | Temp {v['temp']}°C"
            )

        if ctx["recent_notes"]:
            lines.append("RECENT CLINICAL NOTES:")
            for n in ctx["recent_notes"]:
                lines.append(f"  {n['date']}: {n['assessment']} (Plan: {n['plan']})")

        if ctx.get("social_history"):
            lines.append(f"SOCIAL HISTORY: {json.dumps(ctx['social_history'])}")

        if ctx.get("family_history"):
            fh = ctx["family_history"]
            fh_str = json.dumps(fh)[:300]
            lines.append(f"FAMILY HISTORY: {fh_str}")

        return "\n".join(lines)

    def _clinical_lens(self, chief_complaint: str, demographics: Optional[dict]) -> str:
        """Return protocol-level questioning strategy for this complaint + demographic combo.

        Injected into the system prompt so GPT prioritises the right clinical pathway
        rather than relying on generic emergency medicine reasoning.
        """
        c = chief_complaint.lower()
        age: Optional[int] = None
        sex = ""
        if demographics:
            raw_age = demographics.get("age") or demographics.get("age_range", "")
            try:
                age = int(str(raw_age).split("-")[0])
            except Exception:
                pass
            sex = str(demographics.get("sex", "")).lower()

        is_male   = "male" in sex or sex == "m"
        is_female = "female" in sex or sex in ("f", "w")

        lenses: list[str] = []

        # ── CHEST PAIN ────────────────────────────────────────────────
        if any(w in c for w in ["chest", "brust", "thorax", "sternum", "cardiac", "göğüs", "kalp", "iman tahtası"]):
            if age and age >= 45 and is_male:
                lenses.append(
                    "CARDIAC PROTOCOL (Male ≥45): ACS probability is HIGH.\n"
                    "Q1 MUST test diaphoresis (cold sweats) — strongest independent MI predictor.\n"
                    "Q2: Radiation to arm / jaw / back (STEMI pattern).\n"
                    "Q3: Exertional onset vs at rest (unstable angina vs stable).\n"
                    "Q4: Prior cardiac history — previous MI, stent, PCI.\n"
                    "Q5: Onset character — crushing/pressure (ACS) vs tearing (dissection) vs pleuritic (PE/pleuritis).\n"
                    "Deprioritise MSK/GERD unless ACS is convincingly excluded."
                )
            elif is_female and age and age >= 35:
                lenses.append(
                    "FEMALE CHEST PAIN PROTOCOL: Women present atypically — do NOT anchor on 'classic crush'.\n"
                    "Q1: PE risk — recent immobility, surgery, OCP, pregnancy/postpartum.\n"
                    "Q2: Exertional or positional component (pleuritis, pericarditis).\n"
                    "Q3: Aortic dissection screen — worst-ever, tearing quality, hypertension history.\n"
                    "Q4: Associated dyspnoea, palpitations (cardiac, PE).\n"
                    "Q5: Diaphoresis or nausea (atypical ACS presentation in women)."
                )
            else:
                lenses.append(
                    "CHEST PAIN PROTOCOL: Rule out life-threats first.\n"
                    "Q1: Radiation — arm/jaw (ACS), back/tearing (dissection), pleuritic/positional (PE/pleuritis).\n"
                    "Q2: Onset — sudden at maximum (dissection/SAH) vs gradual crescendo (ACS/GERD).\n"
                    "Q3: Positional — worse lying flat (pericarditis) vs worse breathing (PE/pleuritis).\n"
                    "Q4: Diaphoresis or pre-syncope (high-risk features regardless of age).\n"
                    "Q5: Cardiac / coagulation / bleeding history."
                )

        # ── HEADACHE ─────────────────────────────────────────────────
        is_headache = any(w in c for w in ["headache", "head pain", "kopfschmerz", "migraine", "migräne", "baş ağrısı", "başım ağrıyor"])
        has_fever_in_complaint = any(w in c for w in ["fever", "fieber", "temperature", "fièvre", "pyrexia", "ateş", "sıcaklık", "yanıyorum"])

        if is_headache:
            # Combined headache + fever — meningitis/encephalitis/SAH pathway FIRST
            if has_fever_in_complaint:
                lenses.append(
                    "HEADACHE + FEVER PROTOCOL — MENINGITIS / ENCEPHALITIS / SAH:\n"
                    "This combination is a medical emergency until proven otherwise.\n"
                    "THREE MUST-ASK questions before any others:\n"
                    "  1. NECK STIFFNESS — ask if patient cannot touch chin to chest (meningismus).\n"
                    "  2. PHOTOPHOBIA — 'Does bright light make your headache worse?' "
                    "(meningitis triad: headache + fever + photophobia — if all 3 present, EMERGENCY).\n"
                    "  3. PETECHIAL RASH — 'Do you have a rash anywhere on your body, especially "
                    "small red or purple spots that do NOT blanch when pressed?' "
                    "(meningococcaemia — immediately life-threatening, management changes NOW).\n"
                    "Q4: Thunderclap / 'worst headache of your life' — SAH co-exists with infection.\n"
                    "Q5: Altered consciousness / confusion (encephalitis, severe meningitis, cerebral abscess).\n"
                    "NEVER deprioritise rash question — meningococcal purpura = immediate IV benzylpenicillin.\n"
                    "NEVER use 'vision changes' as a substitute for photophobia — they are different findings."
                )
            elif age and age >= 50:
                lenses.append(
                    "HEADACHE PROTOCOL (>=50): Giant cell arteritis AND SAH are must-rule-outs.\n"
                    "Q1: Thunderclap / 'worst headache of life' — SAH until proven otherwise.\n"
                    "Q2: Scalp tenderness or jaw claudication (giant cell arteritis — leads to blindness).\n"
                    "Q3: Focal neurological deficit — vision, speech, limb (stroke, space-occupying lesion).\n"
                    "Q4: Fever + neck stiffness (meningitis — Kernig/Brudzinski signs at risk).\n"
                    "Q5: Gradual progressive worsening over weeks (raised ICP, malignancy)."
                )
            else:
                lenses.append(
                    "HEADACHE PROTOCOL — SNOOP criteria:\n"
                    "Q1: Sudden onset / thunderclap — 'worst headache of life' (SAH until excluded).\n"
                    "Q2: Neurological symptoms — focal weakness, speech, limb weakness (stroke/SOL).\n"
                    "Q3: Systemic signs — fever + neck stiffness + photophobia (meningitis triad).\n"
                    "Q4: Trigger — exertion (SAH/exercise headache), Valsalva, position (Chiari/ICP).\n"
                    "Q5: Pattern change — new type, progressively worsening, or waking from sleep."
                )

        # ── ABDOMINAL PAIN ────────────────────────────────────────────
        if any(w in c for w in ["abdom", "belly", "stomach", "bauch", "nausea", "vomit", "epigast", "pelvic", "karın", "mide", "bulantı", "kusma", "kasık"]):
            if is_female and age and 15 <= age <= 50:
                lenses.append(
                    "ABDOMINAL PAIN PROTOCOL (Female 15–50): ECTOPIC PREGNANCY is life-threatening priority.\n"
                    "Q1: Last menstrual period — is pregnancy possible? If delayed ->IMMEDIATE risk.\n"
                    "Q2: Vaginal bleeding or unusual discharge (ectopic, PID, miscarriage).\n"
                    "Q3: Pain location — right iliac fossa (appendicitis), left (ovarian torsion), diffuse (peritonism).\n"
                    "Q4: Rigidity / guarding / rebound tenderness on movement (peritonitis = surgical).\n"
                    "Q5: Fever + discharge (PID, tubo-ovarian abscess)."
                )
            elif age and age >= 60:
                lenses.append(
                    "ABDOMINAL PAIN PROTOCOL (≥60): Mesenteric ischaemia and AAA are highest-priority.\n"
                    "Q1: Pain out of proportion to examination — patient writhing, diaphoretic (mesenteric ischaemia ->IMMEDIATE).\n"
                    "Q2: Pulsatile abdominal sensation or known AAA (rupture).\n"
                    "Q3: Bloody or dark stool (ischaemia, volvulus, lower GI bleed).\n"
                    "Q4: Epigastric radiation to back (pancreatitis, AAA, posterior ulcer).\n"
                    "Q5: AF / PVD / cardiac history (embolic mesenteric ischaemia, AAA risk)."
                )
            else:
                lenses.append(
                    "ABDOMINAL PAIN PROTOCOL:\n"
                    "Q1: Location + migration — periumbilical ->right iliac fossa (appendicitis classic).\n"
                    "Q2: Character — constant/severe (surgical/inflammatory) vs crampy (obstruction, IBS).\n"
                    "Q3: Movement worsens pain (peritoneal signs = surgical emergency).\n"
                    "Q4: Nausea/vomiting timing relative to pain onset (surgical vs medical).\n"
                    "Q5: Urinary symptoms / flank pain (renal colic mimicking abdomen)."
                )

        # ── SHORTNESS OF BREATH ───────────────────────────────────────
        if any(w in c for w in ["breath", "dyspnoea", "dyspnea", "atemnot", "luftnot", "respiratory", "nefes", "solunum", "boğuluyor", "tıkandı"]):
            lenses.append(
                "DYSPNOEA PROTOCOL:\n"
                "Q1: PE risk — Wells: recent surgery/immobility ≥3 days, DVT history, haemoptysis, HR>100.\n"
                "Q2: Onset — sudden (PE, pneumothorax) vs over hours/days (CHF, pneumonia, COPD exacerbation).\n"
                "Q3: Orthopnoea — worse lying flat / woken at night (CHF, bilateral pleural effusion).\n"
                "Q4: Wheeze vs stridor vs clear (bronchospasm / upper airway obstruction / parenchymal).\n"
                "Q5: Fever + productive cough (pneumonia) vs dry cough + leg swelling (CHF/PE)."
            )

        # ── LEG PAIN / SWELLING ───────────────────────────────────────
        if any(w in c for w in ["leg", "calf", "swelling", "dvt", "bein", "waden", "thrombos", "bacak", "baldır", "şişme", "ödem", "uyluk"]):
            lenses.append(
                "LOWER LIMB PROTOCOL:\n"
                "Q1: Unilateral calf swelling + tenderness + no other explanation (DVT — Wells ≥2 = high risk).\n"
                "Q2: Associated dyspnoea or chest pain (DVT + dyspnoea = PE until excluded ->IMMEDIATE).\n"
                "Q3: Risk factors — immobility >3 days, recent surgery/flight, OCP/HRT, malignancy.\n"
                "Q4: Skin — erythema + warmth (DVT/cellulitis) vs pallor + pulselessness + cold (acute arterial).\n"
                "Q5: Claudication on walking relieved by rest (PAD, especially ≥60)."
            )

        # ── DIZZINESS / SYNCOPE ───────────────────────────────────────
        if any(w in c for w in ["dizz", "vertigo", "faint", "syncop", "schwindel", "ohnmacht", "lightheaded", "baş dön", "bayıl", "gözüm karar", "sersem"]):
            if age and age >= 55:
                lenses.append(
                    "DIZZINESS PROTOCOL (≥55): POSTERIOR STROKE is must-rule-out — HINTS criteria apply.\n"
                    "Q1: Sudden onset with NO positional trigger — central/vascular until excluded.\n"
                    "Q2: Diplopia, facial numbness, dysarthria, dysphagia, limb ataxia (posterior fossa).\n"
                    "Q3: Horizontal nystagmus that DOES NOT suppress with fixation (central sign).\n"
                    "Q4: New-onset severe headache with the dizziness (vertebrobasilar dissection/SAH).\n"
                    "Q5: Palpitations or pre-syncope (cardiac arrhythmia — Holter indication)."
                )
            else:
                lenses.append(
                    "DIZZINESS PROTOCOL:\n"
                    "Q1: True vertigo (room spins) vs pre-syncope (almost fainted) vs imbalance — different paths.\n"
                    "Q2: Positional trigger — specific head movement (BPPV Dix-Hallpike) vs constant (neuritis/central).\n"
                    "Q3: Hearing loss or tinnitus (Ménière's, labyrinthitis, acoustic neuroma).\n"
                    "Q4: Neurological symptoms — diplopia, dysphagia, ataxia (posterior stroke, cerebellar).\n"
                    "Q5: Cardiac history + palpitations (arrhythmia syncope mimicking vertigo)."
                )

        # ── BACK PAIN ─────────────────────────────────────────────────
        if any(w in c for w in ["back pain", "backache", "rückenschmerz", "lumbar", "spine", "low back", "bel ağrısı", "sırt ağrısı", "omurga", "böbrek"]):
            if age and age >= 55 and is_male:
                lenses.append(
                    "BACK PAIN PROTOCOL (Male ≥55): AAA rupture is life-threatening priority.\n"
                    "Q1: Pulsatile/tearing quality + diaphoresis + hypotension feeling (AAA rupture ->IMMEDIATE).\n"
                    "Q2: Cauda equina screen — bladder/bowel incontinence or retention, saddle anaesthesia (SURGICAL EMERGENCY).\n"
                    "Q3: Radiation to groin (renal colic, AAA) vs to leg below knee (disc/nerve root).\n"
                    "Q4: Fever + night sweats + immunosuppression (epidural abscess, vertebral osteomyelitis).\n"
                    "Q5: Known AAA, hypertension, smoking, connective tissue disorder history."
                )
            else:
                lenses.append(
                    "BACK PAIN PROTOCOL:\n"
                    "Q1: Cauda equina screen — bladder/bowel dysfunction, saddle anaesthesia (SURGICAL EMERGENCY).\n"
                    "Q2: Radiation below knee — dermatomal pattern (L4/L5/S1 disc herniation).\n"
                    "Q3: Fever + night sweats + point tenderness (infection, malignancy — red flags).\n"
                    "Q4: Onset — trauma, sudden (fracture) vs insidious progressive (malignancy, infection).\n"
                    "Q5: Progressive bilateral leg weakness or numbness (cord compression — do not miss)."
                )

        # ── STROKE / FOCAL NEUROLOGY ──────────────────────────────────
        if any(w in c for w in ["weakness", "numbness", "speech", "facial drop", "stroke", "schlaganfall", "lähmung", "paralys", "felç", "inme", "uyuşma", "güç kaybı", "peltek"]):
            lenses.append(
                "STROKE PROTOCOL — TIME IS BRAIN:\n"
                "Q1: EXACT last-known-well time — tPA window is 4.5 hours (thrombectomy up to 24 h in selected).\n"
                "Q2: FAST positive — facial droop, arm drift, speech abnormality (if yes ->IMMEDIATE now).\n"
                "Q3: Posterior symptoms — double vision, vertigo, dysphagia, ataxia (basilar artery).\n"
                "Q4: Haemorrhagic features — severe headache, vomiting, very high BP history (ICH vs ischaemic).\n"
                "Q5: Contraindications to thrombolysis — anticoagulants (warfarin/DOAC), recent surgery, active bleeding."
            )

        # ── TRAUMA ────────────────────────────────────────────────────
        if any(w in c for w in ["trauma", "injury", "fall", "wound", "cut", "fracture", "verletz", "hit", "accident", "yaralanma", "kaza", "düştü", "kesik", "kırık", "darbe"]):
            lenses.append(
                "TRAUMA PROTOCOL:\n"
                "Q1: Mechanism — height of fall, vehicle speed, direction of impact (energy = severity).\n"
                "Q2: Loss of consciousness or amnesia around event (TBI regardless of GCS appearance).\n"
                "Q3: Neck or back pain with mechanism (c-spine precautions until cleared).\n"
                "Q4: Hidden injuries — abdominal tenderness, visible haematuria (solid organ / bladder).\n"
                "Q5: Anticoagulants (warfarin, DOAC, aspirin) — minor trauma + anticoagulant = major bleeding risk."
            )

        if not lenses:
            return ""
        return (
            "CLINICAL PROTOCOL FOR THIS PRESENTATION:\n"
            + "\n\n".join(lenses)
        )

    def _personalise_lens(
        self,
        base_lens: str,
        chief_complaint: str,
        structured_ctx: dict,
    ) -> str:
        """Layer patient-specific overrides on top of the generic clinical lens.

        The base lens is derived from complaint + demographics alone.
        This method reads the enriched patient context and adds targeted
        override blocks that take precedence over the base protocol.
        This is where 'generic protocol' becomes 'patient-specific'.
        """
        if not structured_ctx.get("has_history"):
            return base_lens

        overrides: list[str] = []
        c = chief_complaint.lower()
        meds_lower = " ".join(m.lower() for m in structured_ctx.get("active_medications", []))
        conds_lower = " ".join(structured_ctx.get("active_conditions", [])).lower()
        age = structured_ctx.get("age") or 0

        anticoag_set = {"warfarin", "apixaban", "rivaroxaban", "dabigatran", "edoxaban"}
        has_anticoag = any(d in meds_lower for d in anticoag_set)

        alpha1_set = {"tamsulosin", "doxazosin", "alfuzosin"}
        has_alpha1 = any(d in meds_lower for d in alpha1_set)

        beta_set = {"metoprolol", "bisoprolol", "atenolol", "carvedilol", "propranolol"}
        has_beta = any(d in meds_lower for d in beta_set)

        # ANTICOAGULANT + trauma / head / abdominal / back pain
        if has_anticoag and any(w in c for w in ["head", "trauma", "fall", "abdom", "back", "chest", "baş", "darbe", "düşme", "karın", "sırt", "göğüs"]):
            overrides.append(
                "PATIENT-SPECIFIC OVERRIDE — ANTICOAGULATED PATIENT:\n"
                "  This patient is on anticoagulation. The normal 'minor trauma' reassurance does NOT apply.\n"
                "  Q1: Screen for any head trauma in the past 7 days regardless of severity (intracranial bleed risk).\n"
                "  Q2: Any new neurological symptom since the onset (focal weakness, speech change, confusion).\n"
                "  Q3: Evidence of GI bleeding — dark/tarry stools, haematemesis, abdominal pain.\n"
                "  ➔ Lower imaging threshold by at least one category compared to non-anticoagulated patient."
            )

        # ALPHA-1 BLOCKER + dizziness / syncope / fall
        if has_alpha1 and any(w in c for w in ["dizz", "faint", "syncope", "fall", "lightheaded", "black"]):
            overrides.append(
                "PATIENT-SPECIFIC OVERRIDE — ALPHA-1 BLOCKER + POSTURAL SYMPTOMS:\n"
                "  Tamsulosin/doxazosin causes orthostatic hypotension. This is the PRIMARY hypothesis.\n"
                "  Q1: Are symptoms worse on standing or getting up from a seat/bed? (postural trigger)\n"
                "  Q2: Did this happen on first dose or after dose increase?\n"
                "  Q3: Rule out injury from a fall before pursuing cardiac/neuro pathway.\n"
                "  ➔ Cardiac and central pathways are SECONDARY unless postural trigger is convincingly absent."
            )

        # BETA-BLOCKER — masks tachycardia in any acutely ill presentation
        if has_beta and any(w in c for w in ["fever", "infect", "sepsis", "weak", "pale", "unwell"]):
            overrides.append(
                "PATIENT-SPECIFIC OVERRIDE — BETA-BLOCKER MASKS TACHYCARDIA:\n"
                "  Normal or low HR CANNOT be used to exclude shock or sepsis in this patient.\n"
                "  Weight capillary refill, mentation status, blood pressure trend, and skin colour.\n"
                "  Q: Ask specifically about dizziness on exertion — relative bradycardia is the masked signal."
            )

        # DIABETES + vomiting / nausea / abdominal pain — DKA
        if ("diabetes" in conds_lower) and any(w in c for w in ["vomit", "nausea", "diarrh", "abdom", "stomach", "belly"]):
            overrides.append(
                "PATIENT-SPECIFIC OVERRIDE — DIABETIC PATIENT + GI SYMPTOMS (DKA RISK):\n"
                "  DKA is a MUST-NOT-MISS in any diabetic patient with vomiting/nausea/abdominal pain.\n"
                "  Q1: Recent blood glucose reading — was it high (above 14 mmol/L / 250 mg/dL)?\n"
                "  Q2: Is the patient urinating more than usual, or feeling very thirsty? (polyuria/polydipsia = DKA signal)\n"
                "  Q3: Does the breath smell fruity or sweet? (ketone breath)\n"
                "  Q4: Any missed insulin doses or recent illness that could trigger DKA?\n"
                "  ➔ Do NOT attribute vomiting to gastroenteritis until DKA is excluded.\n"
                "  ➔ Dehydration from vomiting worsens DKA — assess fluid intake and urine output."
            )

        # DIABETES + chest / epigastric — silent MI
        if ("diabetes" in conds_lower) and any(w in c for w in ["chest", "epigast", "indigest", "jaw", "arm", "shoulder"]):
            overrides.append(
                "PATIENT-SPECIFIC OVERRIDE — DIABETIC PATIENT + CHEST/EPIGASTRIC COMPLAINT:\n"
                "  Diabetic autonomic neuropathy ->silent MI is common. Chest pain may be mild, absent, or atypical.\n"
                "  Q1: Diaphoresis (cold sweats) — strongest independent MI predictor even in atypical presentations.\n"
                "  Q2: Associated fatigue, dyspnoea, or nausea (diabetic MI triad).\n"
                "  ➔ Lower threshold for ACS work-up regardless of pain intensity."
            )

        # KNOWN MALIGNANCY + back / neurological symptoms
        if any(w in conds_lower for w in ["cancer", "carcinoma", "metasta", "lymphoma", "leukaemia", "myeloma"]):
            if any(w in c for w in ["back", "spine", "leg", "weak", "numb", "bowel", "bladder"]):
                overrides.append(
                    "PATIENT-SPECIFIC OVERRIDE — KNOWN MALIGNANCY + BACK/NEURO SYMPTOMS:\n"
                    "  Spinal cord compression and pathological fracture are IMMEDIATE must-rule-outs.\n"
                    "  Q1: Bowel or bladder dysfunction (new incontinence or retention) — surgical emergency.\n"
                    "  Q2: Saddle anaesthesia or bilateral leg weakness/numbness.\n"
                    "  Q3: Point tenderness on vertebral percussion (metastatic bone lesion).\n"
                    "  ➔ Do not attribute to 'simple mechanical pain' without excluding cord compression first."
                )

        # POST-PROSTATECTOMY / PROSTATE CANCER + leg / chest / breathlessness
        if any(w in conds_lower for w in ["prostatect", "prostate cancer"]):
            if any(w in c for w in ["leg", "calf", "chest", "breath", "swelling"]):
                overrides.append(
                    "PATIENT-SPECIFIC OVERRIDE — POST-PROSTATECTOMY HYPERCOAGULABLE STATE:\n"
                    "  VTE/PE risk is meaningfully elevated post-prostatectomy.\n"
                    "  Q1: Unilateral calf swelling + tenderness (DVT).\n"
                    "  Q2: Associated chest pain or dyspnoea (PE).\n"
                    "  ➔ Treat as high pre-test probability on Wells score."
                )

        # LITHIUM — any non-specific GI / neuro complaint
        if "lithium" in meds_lower:
            overrides.append(
                "PATIENT-SPECIFIC OVERRIDE — LITHIUM THERAPY:\n"
                "  Narrow therapeutic index. Any dehydration, AKI, new drug, or reduced fluid intake\n"
                "  can precipitate lithium toxicity (tremor, confusion, GI, seizure).\n"
                "  Q: Recent fluid intake change, new medications, vomiting, or diarrhoea?\n"
                "  ➔ Toxicity must be on the differential for any neuro/GI/renal complaint."
            )

        # DIGOXIN — any GI / visual / rhythm complaint
        if "digoxin" in meds_lower:
            overrides.append(
                "PATIENT-SPECIFIC OVERRIDE — DIGOXIN THERAPY:\n"
                "  Toxicity is precipitated by dehydration, AKI, or hypokalaemia.\n"
                "  Q: Nausea, vomiting, visual disturbance (yellow/green tinge), or palpitations?\n"
                "  ➔ GI/visual symptoms in a digoxin patient = toxicity screen immediately."
            )

        # CLOZAPINE — any systemic complaint
        if "clozapine" in meds_lower:
            overrides.append(
                "PATIENT-SPECIFIC OVERRIDE — CLOZAPINE THERAPY:\n"
                "  Agranulocytosis risk: fever or infection in clozapine patient = FBC urgently.\n"
                "  Myocarditis risk in first 6 months: chest pain + tachycardia = urgent cardiac screen.\n"
                "  ➔ Any acute presentation in clozapine patient escalates one triage tier."
            )

        # GERIATRIC + POLYPHARMACY — non-specific complaint
        n_meds = len(structured_ctx.get("active_medications", []))
        if age >= 75 and n_meds >= 4:
            overrides.append(
                f"PATIENT-SPECIFIC OVERRIDE — GERIATRIC PATIENT ({age}yo, {n_meds} medications):\n"
                "  Atypical presentations are the norm. Pain reporting is unreliable.\n"
                "  Screen for: delirium (acute confusion onset), occult infection (no fever possible),\n"
                "  drug-drug interactions (recent prescription change?), fall risk.\n"
                "  ➔ Do not anchor on the most obvious explanation without geriatric overlay."
            )

        if not overrides:
            return base_lens

        return (
            base_lens
            + ("\n\n" if base_lens else "")
            + "═══════════════════════════════════════════════════════\n"
            + "PATIENT-SPECIFIC OVERRIDES — TAKE PRIORITY OVER BASE PROTOCOL\n"
            + "═══════════════════════════════════════════════════════\n"
            + "\n\n".join(overrides)
        )

    # ------------------------------------------------------------------
    # Dynamic question generation (Agentic AI)
    # ------------------------------------------------------------------

    def _validate_question(self, q: dict) -> tuple[bool, str]:
        """Gen-time structural validator. Runs before a question reaches the patient.
        Returns (True, '') if valid or (False, reason) if it must be rejected/retried."""
        if not q:
            return False, "question object is None"

        text  = (q.get("question") or "").strip()
        qtype = (q.get("type") or "").strip()

        if not text:
            return False, "empty question text"

        if qtype not in ("yes_no", "multiple_choice", "scale", "photo_request", "free_text"):
            return False, f"unknown type '{qtype}'"

        text_lower = text.lower()

        if qtype == "yes_no":
            # OR-finding rule — check both the displayed question AND question_en
            if _re.search(r"\bor\b", text_lower) or _re.search(r"\bor\b", text_en_check):
                return False, "yes_no contains 'or' — use multiple_choice with findings as options in patient's language"
            # 2+ findings with 'and'
            _finding_words = r"(?:pain|swelling|fever|nausea|vomit|cough|bleed|dizziness|shortness|breath|headache|weak|numb|rash|bruise)"
            if _re.search(_finding_words + r".*\band\b.*" + _finding_words, text_lower):
                return False, "yes_no combines two findings with 'and' — split into separate questions"
            # comma list
            if text.count(",") >= 2:
                return False, "yes_no with comma-listed findings — use multiple_choice"

        if qtype == "scale":
            intensity_words = {"pain", "intensity", "severe", "rate", "scale", "discomfort", "hurt"}
            if not any(w in text_lower for w in intensity_words):
                return False, "scale type used for non-intensity question — reconsider type"

        options = q.get("options") or []
        if qtype in ("yes_no", "multiple_choice", "scale") and not options:
            return False, f"type '{qtype}' requires non-empty options"

        if qtype == "yes_no" and options:
            _informal = {"nope", "yep", "yeah", "sure", "correct", "negative", "affirmative"}
            bad = [o for o in options if str(o).lower() in _informal]
            if bad:
                return False, f"yes_no options contain informal forms {bad} — use Yes/No or language equivalent"

        if qtype == "multiple_choice" and options:
            fragment_opts = [o for o in options if str(o).strip().endswith("?")]
            if fragment_opts:
                return False, f"multiple_choice options contain question fragments: {fragment_opts}"

        return True, ""

    # ---------------------------------------------------------------------------
    # Clinical dimensions — complaint-specific coverage tracking
    # ---------------------------------------------------------------------------

    _COMPLAINT_DIMENSIONS: dict[str, list[str]] = {
        "chest":     ["character", "onset", "radiation", "diaphoresis", "exertional", "cardiac_history"],
        "headache":  ["onset_type", "character", "neuro_symptoms", "systemic", "pattern_change"],
        "abdominal": ["location", "character", "onset", "peritoneal_signs", "associated_gi"],
        "breath":    ["onset", "character", "orthopnoea", "pe_risk", "fever_cough"],
        "dyspnoea":  ["onset", "character", "orthopnoea", "pe_risk", "fever_cough"],
        "vomit":     ["frequency", "blood_in_vomit", "associated_pain", "hydration_status", "fever", "duration"],
        "nausea":    ["associated_vomiting", "associated_pain", "hydration_status", "fever", "duration"],
        "diarrhea":  ["frequency", "blood_in_stool", "associated_pain", "hydration_status", "fever", "duration"],
        "diarrhoea": ["frequency", "blood_in_stool", "associated_pain", "hydration_status", "fever", "duration"],
        "leg":       ["unilateral_swelling", "associated_breathing", "dvt_risk", "skin_changes", "claudication"],
        "dizziness": ["type", "positional", "hearing", "neuro_symptoms", "cardiac"],
        "syncope":   ["trigger", "prodrome", "duration", "neuro_symptoms", "cardiac"],
        "back":      ["cauda_equina", "radiation", "systemic", "mechanism", "character"],
        "stroke":    ["last_known_well", "fast_screen", "posterior_symptoms", "haemorrhagic", "contraindications"],
        "trauma":    ["mechanism", "loc", "spine", "hidden_injuries", "anticoag"],
        "weakness":  ["distribution", "onset", "associated_symptoms", "last_known_well", "pain"],
        "fever":     ["systemic_source", "rigors", "localising_symptoms", "immunocompromise", "travel"],
    }

    def _required_dimensions(self, chief_complaint: str) -> list[str]:
        """Return the clinical dimensions that must be covered for this complaint."""
        c = chief_complaint.lower()
        for key, dims in self._COMPLAINT_DIMENSIONS.items():
            if key in c:
                return dims
        return ["onset", "character", "severity", "associated_symptoms", "relevant_history"]

    def _extract_covered_findings(self, previous_answers: list[dict]) -> dict[str, str]:
        """Parse answered questions to build a findings-covered map.
        Maps dimension name ->'positive'|'negative'|'answered' so we know
        which clinical areas no longer need probing."""
        covered: dict[str, str] = {}
        for ans in previous_answers:
            q_text = (ans.get("question") or "").lower()
            answer  = str(ans.get("answer") or "").lower()
            dim     = (ans.get("tested_dimension") or "").strip()
            if dim:
                covered[dim] = "positive" if any(
                    w in answer for w in ["yes", "positive", "severe", "crushing", "tearing"]
                ) else "answered"
                continue
            # fallback: keyword heuristic
            if any(w in q_text for w in ["radiation", "radiat", "spread", "jaw", "arm"]):
                covered["radiation"] = "answered"
            if any(w in q_text for w in ["sweat", "diaphoresis", "cold sweat"]):
                covered["diaphoresis"] = "positive" if "yes" in answer else "negative"
            if any(w in q_text for w in ["exertion", "exertional", "effort", "walking"]):
                covered["exertional"] = "answered"
            if any(w in q_text for w in ["onset", "start", "begin", "when"]):
                covered["onset"] = "answered"
            if any(w in q_text for w in ["charact", "describ", "type", "quality", "nature"]):
                covered["character"] = "answered"
            if any(w in q_text for w in ["bowel", "bladder", "incontinence"]):
                covered["cauda_equina"] = "answered"
            if any(w in q_text for w in ["last known well", "when did", "time"]):
                covered["last_known_well"] = "answered"
            if any(w in q_text for w in ["cardiac", "heart", "previous mi", "stent"]):
                covered["cardiac_history"] = "answered"
            if any(w in q_text for w in ["dvt", "clot", "immob", "travel", "surgery"]):
                covered["dvt_risk"] = "answered"
            if any(w in q_text for w in ["neuro", "weakness", "speech", "vision", "facial"]):
                covered["neuro_symptoms"] = "answered"
        return covered

    def _question_budget(
        self,
        hypothesis: dict,
        covered: dict,
        required_dims: list[str],
        n_asked: int,
        chief_complaint: str,
    ) -> dict:
        """Compute adaptive question budget for this turn."""
        budget_min = 3
        budget_max = 7

        # Elevate minimum for high-stakes hypotheses
        must_not_miss = hypothesis.get("must_not_miss", [])
        high_stakes = {"ACS", "dissection", "SAH", "PE", "aortic", "cord compression", "stroke"}
        if any(any(h in d for h in high_stakes) for d in must_not_miss):
            budget_min = 4

        missing_dims = [d for d in required_dims if d not in covered]

        # High-confidence emergency stop — classic ACS + diaphoresis positive etc.
        high_confidence_emergency = (
            n_asked >= budget_min
            and covered.get("diaphoresis") == "positive"
            and covered.get("radiation") in ("answered", "positive")
            and any(w in chief_complaint.lower() for w in ["chest", "cardiac"])
        )

        all_dims_covered = not missing_dims and n_asked >= budget_min
        at_max = n_asked >= budget_max
        should_stop = high_confidence_emergency or all_dims_covered or at_max

        stop_reason = ""
        if high_confidence_emergency:
            stop_reason = "high_confidence_emergency"
        elif all_dims_covered:
            stop_reason = "all_dimensions_covered"
        elif at_max:
            stop_reason = "max_budget_reached"

        return {
            "min": budget_min,
            "max": budget_max,
            "missing_dims": missing_dims,
            "should_stop_eligible": should_stop,
            "stop_reason": stop_reason,
        }

    def _session_cache_key(
        self,
        chief_complaint: str,
        medical_history: Optional[dict],
        demographics: Optional[dict],
    ) -> str:
        """Stable cache key — based on complaint + history identity (not full hash for perf)."""
        import hashlib
        raw = chief_complaint + str(sorted((demographics or {}).items()))
        if medical_history:
            # Use patient id + complaint so a new complaint invalidates the cache
            pat = medical_history.get("patient") or medical_history.get("demographics") or {}
            raw += str(pat.get("id") or pat.get("first_name", "") + pat.get("last_name", ""))
        return hashlib.md5(raw.encode()).hexdigest()[:16]

    def _build_pre_assessment_hypothesis(
        self,
        chief_complaint: str,
        medical_history: Optional[dict],
        demographics: Optional[dict],
        structured_ctx: Optional[dict] = None,
    ) -> dict:
        """Build a rich clinical hypothesis dict cached for the full session.

        Called once per patient-complaint session, then reused every turn.
        Returns a dict (not a string) so callers can access individual fields
        for adaptive budget calculation, questioning strategy, etc.

        Schema:
            primary_hypothesis        — most likely Dx
            secondary_hypotheses      — ≤3 alternative Dx in priority order
            must_not_miss             — life-threats to actively rule out
            history_driven_concerns   — each: {factor, mechanism, test_question_topic}
            questioning_strategy      — one-sentence priority approach
            low_probability_dismissed — diagnoses ruled out by history
        """
        _empty = {
            "primary_hypothesis":      "Unknown — no history available",
            "secondary_hypotheses":    [],
            "must_not_miss":           [],
            "history_driven_concerns": [],
            "questioning_strategy":    "Ask broad screening questions first.",
            "low_probability_dismissed": [],
        }

        if not medical_history:
            return _empty

        if not self._initialized:
            return {
                "primary_hypothesis":      f"Pre-assessment (mock): complaint={chief_complaint}",
                "secondary_hypotheses":    [],
                "must_not_miss":           [],
                "history_driven_concerns": [],
                "questioning_strategy":    "Proceed with targeted questioning.",
                "low_probability_dismissed": [],
            }

        ctx = structured_ctx or self._structured_patient_context(medical_history, chief_complaint)
        ctx_str = self._format_structured_context(ctx)

        demo_note = ""
        if demographics:
            age = demographics.get("age_range") or demographics.get("age", "")
            sex = demographics.get("sex", "")
            demo_note = f"Patient: {sex}, {age}."

        hypothesis_prompt = f"""You are a senior emergency physician performing a 30-second bedside
pre-assessment before your first question. You have the patient's full enriched medical history
and their current chief complaint. Reason like an experienced clinician — not a protocol robot.

{demo_note}

[ENRICHED PATIENT CONTEXT — already interpreted, treat as truth]
{ctx_str}

[CURRENT CHIEF COMPLAINT]
{chief_complaint}

YOUR TASK — produce a JSON hypothesis object:

1. PRIMARY HYPOTHESIS: The single most likely diagnosis given this patient's specific history + complaint.
   Do NOT default to the statistically commonest cause — adjust for THIS patient's risk profile.

2. SECONDARY HYPOTHESES: Up to 3 alternative diagnoses in descending probability order.

3. MUST NOT MISS: Up to 3 immediately life-threatening diagnoses you must actively rule out,
   even if currently less likely. Include WHY based on this patient's history.

4. HISTORY-DRIVEN CONCERNS: For each relevant history item (medication, condition, past procedure),
   state: the history factor, the clinical mechanism it creates, and the specific question topic
   that would test for it. Only include items genuinely relevant to this complaint.

5. QUESTIONING STRATEGY: One sentence on how this patient's history should bias your question order
   compared to a generic patient with the same complaint.

6. LOW PROBABILITY DISMISSED: Diagnoses that would normally be in the differential but are
   significantly less likely given this patient's specific history (explain why).

Respond ONLY with valid JSON — no prose, no code fences:
{{
  "primary_hypothesis": "...",
  "secondary_hypotheses": ["...", "..."],
  "must_not_miss": [
    {{"condition": "...", "reason": "..."}},
    {{"condition": "...", "reason": "..."}}
  ],
  "history_driven_concerns": [
    {{"factor": "...", "mechanism": "...", "test_question_topic": "..."}},
    {{"factor": "...", "mechanism": "...", "test_question_topic": "..."}}
  ],
  "questioning_strategy": "...",
  "low_probability_dismissed": [
    {{"condition": "...", "reason": "..."}}
  ]
}}"""

        try:
            response_content = self._chat_complete(
                messages=[{"role": "user", "content": hypothesis_prompt}],
                max_tokens=700,
            )
            cleaned = response_content.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("```")[1]
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]
                cleaned = cleaned.strip()
            hyp = json.loads(cleaned)
            logger.info(
                "Pre-assessment hypothesis built: primary='%s' must_not_miss=%s",
                str(hyp.get("primary_hypothesis", ""))[:80],
                [m.get("condition") if isinstance(m, dict) else m for m in hyp.get("must_not_miss", [])],
            )
            return hyp
        except Exception as exc:
            logger.warning("Hypothesis generation failed (%s) — returning empty frame.", exc)
            return _empty

    def generate_next_question(
        self,
        chief_complaint: str,
        previous_answers: list[dict],
        demographics: Optional[dict] = None,
        medical_history: Optional[dict] = None,
        target_language: Optional[str] = None,
    ) -> dict:
        """Generate ONE high-yield clinical follow-up question per call.

        Architecture (history-aware, patient-specific):
        Step 0 — Enrich demographics from medical history.
        Step 1 — Build structured patient context (deterministic code enrichment).
        Step 2 — Get or build session-cached clinical hypothesis (LLM, once per session).
        Step 3 — Build personalised clinical lens (base protocol + patient-specific overrides).
        Step 4 — Compute adaptive question budget (min/max + dimension coverage).
        Step 5 — Build system prompt with all context layers.
        Step 6 — Call LLM, validate output, retry once on structural failure.
        """
        if not self._initialized:
            count = len(previous_answers)
            if count >= 5:
                return {"done": True, "question": None}
            mock_qs = [
                "Are you in severe pain?",
                "Do you have a high fever?",
                "Is it difficult to breathe?",
                "Do you feel dizzy or faint?",
                "Do you have any known medical conditions?",
            ]
            q_text = mock_qs[count] if count < len(mock_qs) else "Any other symptoms?"
            return {
                "done": False,
                "question": {
                    "question": q_text,
                    "type": "yes_no",
                    "options": ["Yes", "No"],
                    "clinical_rationale": "mock fallback",
                },
            }

        # ── Step 0: Enrich demographics from medical history ─────────────────
        if medical_history:
            pat = medical_history.get("patient") or medical_history.get("demographics") or {}
            demographics = dict(demographics or {})
            if pat.get("sex") and not demographics.get("sex"):
                demographics["sex"] = pat["sex"]
            if pat.get("date_of_birth"):
                try:
                    exact_age = datetime.now(timezone.utc).year - int(str(pat["date_of_birth"])[:4])
                    demographics["age"] = exact_age
                except Exception:
                    pass
            if pat.get("blood_type") and not demographics.get("blood_type"):
                demographics["blood_type"] = pat["blood_type"]
            if pat.get("nationality") and not demographics.get("nationality"):
                demographics["nationality"] = pat["nationality"]

        # ── Step 1: Structured patient context (deterministic, code-level) ───
        structured_ctx = self._structured_patient_context(medical_history, chief_complaint)
        structured_ctx_text = self._format_structured_context(structured_ctx)

        # ── Step 2: Session-cached hypothesis (LLM call, once per session) ───
        cache_key = self._session_cache_key(chief_complaint, medical_history, demographics)
        if cache_key not in self._hypothesis_cache:
            hyp = self._build_pre_assessment_hypothesis(
                chief_complaint, medical_history, demographics, structured_ctx
            )
            self._hypothesis_cache[cache_key] = hyp
        hypothesis = self._hypothesis_cache[cache_key]

        # ── Step 3: Personalised clinical lens ───────────────────────────────
        base_lens    = self._clinical_lens(chief_complaint, demographics)
        clinical_lens = self._personalise_lens(base_lens, chief_complaint, structured_ctx)

        # ── Step 4: Adaptive question budget ─────────────────────────────────
        guidelines, _, _rag_sources = self._retrieve_context(chief_complaint)
        n_asked        = len(previous_answers)
        required_dims  = self._required_dimensions(chief_complaint)
        covered        = self._extract_covered_findings(previous_answers)
        budget         = self._question_budget(hypothesis, covered, required_dims, n_asked, chief_complaint)

        # Hard stop — max budget reached
        if n_asked >= budget["max"]:
            return {"done": True, "question": None, "stop_reason": "max_budget_reached"}

        # Format hypothesis for prompt
        must_not_miss_list = [
            (m.get("condition") + " — " + m.get("reason", "")) if isinstance(m, dict) else str(m)
            for m in hypothesis.get("must_not_miss", [])
        ]
        history_concerns_lines = "\n".join(
            f"  • {c.get('factor','?')} ->{c.get('mechanism','?')} "
            f"[test topic: {c.get('test_question_topic','?')}]"
            for c in hypothesis.get("history_driven_concerns", [])
            if isinstance(c, dict)
        ) or "  (none — no notable history-complaint interactions)"

        covered_str = ", ".join(f"{k}({v})" for k, v in covered.items()) if covered else "none yet"
        missing_str = ", ".join(budget["missing_dims"]) if budget["missing_dims"] else "all covered"

        if budget["should_stop_eligible"]:
            budget_rule = (
                f"STOP DECISION: You MAY return done:true now (reason: {budget['stop_reason']}).\n"
                f"Do so only if you have a confident clinical picture. If one high-value question\n"
                f"remains, ask it and stop after that answer."
            )
        else:
            budget_rule = (
                f"CONTINUE: Return done:false with the next best question.\n"
                f"Questions asked so far: {n_asked}. Minimum before stop: {budget['min']}."
            )

        # ── Step 5a: Language generation instruction ─────────────────────────
        # Turkish (tr) and German (de): generate the question DIRECTLY in the target
        # language — GPT writes as a native triage nurse, no separate translation step.
        # All other languages: English only (question == question_en).
        _tl = (target_language or "").lower()
        _tl_base = _tl.split("-")[0]

        _LANG_GENERATION_GUIDES: dict[str, tuple[str, str]] = {
            "tr": (
                "Turkish",
                "You are an experienced Turkish triage nurse (triaj hemşiresi).\n"
                "Generate the 'question' field DIRECTLY in Turkish — do NOT translate from English.\n"
                "Write exactly as you would speak to an anxious patient in a Turkish ER.\n"
                "STYLE RULES:\n"
                "  • Always use formal 'siz' form. Every question ends with '?'\n"
                "  • Simple everyday Turkish — 8th-grade level. Never medical jargon.\n"
                "  • Preferred terms: 'ağrı' (not nosisepsyon), 'nefes darlığı' (not dispne),\n"
                "    'baş dönmesi' (not vertigo), 'bulantı' (not nausea), 'halsizlik',\n"
                "    'ışığa hassasiyet' (not fotofobi), 'boyun sertliği' (not meningismus),\n"
                "    'döküntü'/'kırmızı lekeler' (not peteşi), 'titreme' (not rijor),\n"
                "    'kollarınızda/bacaklarınızda güçsüzlük' (never 'uzuv zayıflığı')\n"
                "  • Onset: 'Baş ağrınız aniden mi başladı?' (NOT 'Ani başlangıçla oluyor mu?')\n"
                "  • State/condition questions: NEVER use 'ne hale getiriyor' or 'sizi ne yapıyor'.\n"
                "    Ask directly: 'Kendinizi nasıl hissediyorsunuz?' / 'Şu anki durumunuzu nasıl\n"
                "    tanımlarsınız?' / 'Şu anda ne yaşıyorsunuz?'\n"
                "  • yes_no options MUST be exactly: ['Evet', 'Hayır']\n"
                "  • For multiple_choice: use 'Her ikisi de' (Both), 'Hiçbiri' (None/Neither)\n"
                "  • Other options in natural Turkish: 'Emin değilim', 'Şimdi başladı',\n"
                "    '1 saatten az', '1-6 saat', '6-24 saat', 'Hafif', 'Orta', 'Şiddetli'\n\n"
                "CRITICAL — ALL options MUST be in Turkish. NEVER mix Turkish question with English options.\n"
                "  ❌ WRONG: options: ['Swelling of your lips', 'Tongue', 'Throat', 'Hiçbiri']\n"
                "  ✅ CORRECT: options: ['Dudaklarımda', 'Dilimde', 'Boğazımda', 'Hiçbirinde']\n\n"
                "  ❌ WRONG: options: ['Did you faint', 'Have a seizure', 'Her ikisi de', 'Hiçbiri']\n"
                "  ✅ CORRECT: options: ['Bayıldım', 'Nöbet geçirdim', 'Her ikisi de', 'Hiçbiri']\n\n"
                "  ❌ WRONG: options: ['Weakness in your arms', 'In your legs', 'Both', 'Neither']\n"
                "  ✅ CORRECT: options: ['Kollarımda', 'Bacaklarımda', 'Her ikisinde de', 'Hiçbirinde']"
            ),
            "de": (
                "German",
                "You are an experienced German triage nurse (Notfallpflegekraft).\n"
                "Generate the 'question' field DIRECTLY in German — do NOT translate from English.\n"
                "Write exactly as you would speak to an anxious patient in a German ER.\n"
                "STYLE RULES:\n"
                "  • Always use formal 'Sie' form. Every question ends with '?'\n"
                "  • Simple everyday German — NOT medical Fachsprache.\n"
                "  • Preferred terms: 'Schmerz' (not Algodynie), 'Kurzatmigkeit' (not Dyspnoe),\n"
                "    'Schwindel' (not Vertigo), 'Übelkeit' (not Nausea),\n"
                "    'Ohnmacht' (not Synkope), 'Ausschlag' (not Exanthem), 'Zittern' (not Rigor)\n"
                "  • yes_no options MUST be exactly: ['Ja', 'Nein']\n"
                "  • For multiple_choice: use 'Beides' (Both), 'Keines davon' (None/Neither)\n"
                "  • Other options in natural German: 'Bin nicht sicher', 'Gerade eben',\n"
                "    'Vor weniger als 1 Stunde', '1–6 Stunden', 'Leicht', 'Mittel', 'Stark'\n\n"
                "CRITICAL — ALL options MUST be in German. NEVER mix German question with English options.\n"
                "  ❌ WRONG: options: ['Swelling of your lips', 'Tongue', 'Throat', 'Keines davon']\n"
                "  ✅ CORRECT: options: ['Lippen', 'Zunge', 'Rachen', 'Keines davon']\n\n"
                "  ❌ WRONG: options: ['Did you faint', 'Have a seizure', 'Beides', 'Keines davon']\n"
                "  ✅ CORRECT: options: ['Ohnmacht', 'Krampfanfall', 'Beides', 'Keines davon']"
            ),
        }

        lang_entry = _LANG_GENERATION_GUIDES.get(_tl_base)
        needs_localisation = bool(lang_entry and not _tl_base.startswith("en"))

        if needs_localisation:
            lang_display, lang_style = lang_entry
            language_instruction = (
                f"LANGUAGE — {lang_display.upper()}:\n"
                f"{lang_style}\n\n"
                f"FIELDS:\n"
                f"  • 'question'    → the question in {lang_display} "
                f"(native generation — NOT a translation of English)\n"
                f"  • 'question_en' → the same question restated in English "
                f"(required for backend logging)\n"
                f"  • 'options'     → answer options in {lang_display} (follow style rules above)\n"
            )
            translation_field_note = f" — in {lang_display} (native generation)"
            translation_options_note = f" — in {lang_display}"
        else:
            language_instruction = (
                "LANGUAGE: English only. "
                "Set 'question' and 'question_en' to the same English text. "
                "Options in English.\n"
            )
            translation_field_note = " — in English"
            translation_options_note = ""

        # ── Step 5b: System prompt — all layers ──────────────────────────────
        system_prompt = f"""You are AIVoN, a senior emergency-medicine clinical reasoning engine.
Your task: produce ONE high-yield triage question that maximally advances the clinical picture.
Think like a consultant ED physician at the bedside — not like a checklist reader.

══════════════════════════════════════════════════════════════════════════
SECTION 1 — STRUCTURED PATIENT CONTEXT (code-interpreted, treat as truth)
══════════════════════════════════════════════════════════════════════════
{structured_ctx_text}

══════════════════════════════════════════════════════════════════════════
SECTION 2 — CLINICAL PRE-ASSESSMENT HYPOTHESIS (your reasoning frame)
══════════════════════════════════════════════════════════════════════════
PRIMARY HYPOTHESIS:   {hypothesis.get('primary_hypothesis', 'Unknown')}
SECONDARY HYPOTHESES: {', '.join(hypothesis.get('secondary_hypotheses', []) or ['—'])}
MUST NOT MISS:
{chr(10).join('  ⚠ ' + m for m in must_not_miss_list) or '  —'}

HISTORY-DRIVEN CONCERNS — at least ONE must be tested in your first 3 questions:
{history_concerns_lines}

QUESTIONING STRATEGY: {hypothesis.get('questioning_strategy', 'Standard EM approach.')}

══════════════════════════════════════════════════════════════════════════
SECTION 3 — CLINICAL LENS + PATIENT-SPECIFIC OVERRIDES
══════════════════════════════════════════════════════════════════════════
{clinical_lens if clinical_lens else "Apply evidence-based emergency medicine principles."}

══════════════════════════════════════════════════════════════════════════
SECTION 4 — RAG GUIDELINES
══════════════════════════════════════════════════════════════════════════
{guidelines if guidelines else "No specific RAG protocol retrieved. Apply evidence-based EM principles."}

══════════════════════════════════════════════════════════════════════════
SECTION 5 — CONVERSATION STATE
══════════════════════════════════════════════════════════════════════════
Chief complaint:        {chief_complaint}
Demographics:           {json.dumps(demographics or {})}
Questions asked so far: {n_asked}
Required dimensions:    {', '.join(required_dims)}
Already covered:        {covered_str}
Still missing:          {missing_str}

Transcript (do NOT repeat or re-ask any of these):
{json.dumps(previous_answers, indent=2)}

══════════════════════════════════════════════════════════════════════════
SECTION 6 — ADAPTIVE QUESTION BUDGET
══════════════════════════════════════════════════════════════════════════
Minimum before stop: {budget['min']} | Maximum hard ceiling: {budget['max']}
{budget_rule}

══════════════════════════════════════════════════════════════════════════
SECTION 7 — DECISION RULES
══════════════════════════════════════════════════════════════════════════
• Choose the question whose answer would most change the triage classification OR
  rule in/out a MUST-NOT-MISS diagnosis OR test a HISTORY-DRIVEN CONCERN.
• Follow the CLINICAL LENS question order where unasked dimensions remain.
• PATIENT-SPECIFIC OVERRIDES in Section 3 take priority over the base lens.
• If a known chronic condition exists, ask about acute complications first.
• For visible injuries (cut, burn, rash, bleeding) with no photo in transcript:
  set type to "photo_request".

══════════════════════════════════════════════════════════════════════════
SECTION 7b — PATIENT-COMPREHENSIBILITY RULES (HARD RULES)
══════════════════════════════════════════════════════════════════════════
The patient is a non-medical person in distress. Every word must be understandable
to someone with no medical training.

❌ FORBIDDEN — clinical examination terminology the patient cannot understand:
  • "out of proportion to touch" / "out of proportion to examination"
    → instead ask: "Is your pain MUCH worse when someone touches or presses on your belly?"
  • "peritoneal signs" / "peritonism" / "rebound tenderness"
    → instead ask: "Does the pain get sharper when you release pressure from your belly?"
  • "meningismus" / "meningeal irritation"
    → instead ask: "Is it painful to move your head forward or tuck your chin to your chest?"
  • "guarding" / "voluntary guarding"
    → instead ask: "Do you tense your stomach muscles because you're afraid of the pain?"
  • Any Latin medical term or clinical examination finding the patient cannot self-report.

❌ FORBIDDEN — anatomically contradictory phrasing:
  • NEVER describe pain as being in TWO different locations in the same question.
  • WRONG: "Do you have abdominal pain in your back?" — abdomen and back are different anatomical regions.
  • CORRECT (radiation): "Does the pain spread or travel to your back?"
  • CORRECT (location): Use multiple_choice with all location options as separate items.

❌ FORBIDDEN — non-standard severity terminology:
  • "Lightweight" → use "Mild"
  • "Heavy" (for pain severity) → use "Severe"
  • "A lot of pain" → use "Severe"
  • MANDATORY severity scale: ["Mild", "Moderate", "Severe"] — no variations allowed.

❌ FORBIDDEN — vague temporal terms:
  • "Recently" → specify: "In the last hour?" / "In the last 24 hours?"
  • "Often" → specify: "More than 3 times?" / "Every few minutes?"

══════════════════════════════════════════════════════════════════════════
SECTION 8 — ONE FINDING PER QUESTION (HARD RULE)
══════════════════════════════════════════════════════════════════════════
Each question tests EXACTLY ONE clinical finding.

❌ FORBIDDEN in yes_no type:
  • Any "or" between findings:      "Pain or breathlessness?"
  • Any "and" between findings:     "Pain and swelling?"
  • Comma-separated finding list:   "Nausea, vomiting, diarrhoea?"

✅ CORRECT for related findings — use multiple_choice, findings become options:
  question: "Which of these do you have right now?"
  type: "multiple_choice"
  options: ["Chest pain", "Shortness of breath", "Cold sweats", "None of these"]

  question: "How did your symptoms start?"
  type: "multiple_choice"
  options: ["Suddenly (seconds)", "Over minutes", "Over hours", "Over days"]

OPTIONS MUST BE SHORT STANDALONE LABELS (1–5 words):
  ❌ WRONG — fragment of the question:  "Weakness in your arms right now"
  ❌ WRONG — a question as option:      "Do you have leg weakness?"
  ❌ WRONG — possessive noise:          "Your fever", "Your pain"
  ✅ CORRECT — clean noun labels:       "Arms", "Legs", "Both", "Neither"
  ✅ CORRECT — clean symptom labels:    "Fever", "Neck stiffness", "Both", "Neither"
  ✅ CORRECT — clean time labels:       "Just now", "Within 1 hour", "1–6 hours"

══════════════════════════════════════════════════════════════════════════
SECTION 9 — QUESTION TYPE RULES
══════════════════════════════════════════════════════════════════════════
• yes_no       — ONE binary finding only.
  English: options=["Yes","No"] exactly — NEVER "Yep", "Nope", "Sure", "Correct".
  Turkish: options=["Evet","Hayır"]. German: options=["Ja","Nein"].
• multiple_choice — ≥3 value categories OR ≥2 related findings as options.
  MANDATORY for: pain location, radiation pattern, onset timing, pain character,
  aggravating/relieving factors, screening ≥2 associated symptoms.
  Always end with "None of these" as the negative option.
  ⚠ Location questions MUST always be multiple_choice — there are always ≥3 possible
    locations. A yes_no for location is ALWAYS wrong.
• scale         — ONLY numeric intensity (1–10). options=["1"…"10"].
• photo_request — ONLY for visible findings without an existing image.
• free_text     — FORBIDDEN. Patient is in distress and cannot type.

══════════════════════════════════════════════════════════════════════════
SECTION 10 — OUTPUT FORMAT (strict JSON only — no prose, no code fences)
══════════════════════════════════════════════════════════════════════════
{language_instruction}
{{
  "done": <bool>,
  "question": null | {{
    "question": "<≤15 words, ONE finding, patient-friendly{translation_field_note}>",
    "question_en": "<same question in English — always required>",
    "options": [...{translation_options_note}],
    "type": "yes_no" | "multiple_choice" | "scale" | "photo_request",
    "clinical_rationale": "<1 sentence: which hypothesis/dimension/concern this tests>",
    "tested_dimension": "<one required dimension from Section 5, e.g. 'radiation'>",
    "tests_history_concern": "<factor name from Section 2 history-driven concerns, or null>"
  }},
  "stop_reason": "<if done:true — one of: all_dimensions_covered, high_confidence_emergency, max_budget_reached>"
}}"""

        # ── Step 6: Build user message; attach images if present ─────────────
        has_images = any(ans.get("image") for ans in previous_answers)

        if has_images:
            content: list[dict] = [
                {
                    "type": "text",
                    "text": (
                        f"Patient complaint: {chief_complaint}\n\n"
                        f"Assessment so far:\n{json.dumps(previous_answers, indent=2)}"
                    ),
                }
            ]
            for ans in previous_answers:
                if ans.get("image"):
                    b64 = ans["image"]
                    if not b64.startswith("data:image"):
                        b64 = f"data:image/jpeg;base64,{b64}"
                    content.append({"type": "image_url", "image_url": {"url": b64}})
        else:
            content = (
                f"Patient complaint: {chief_complaint}\n\n"
                f"Assessment so far:\n{json.dumps(previous_answers, indent=2)}"
            )

        # ── Step 7: Call LLM, validate, retry once if structurally invalid ───
        _fallback_questions = [
            "Are you in severe pain right now?",
            "Do you have a high fever?",
            "Is it difficult to breathe?",
            "Do you feel dizzy or faint?",
            "Have you had any loss of consciousness?",
        ]

        def _call_and_parse(prompt: str) -> Optional[dict]:
            rc = self._chat_complete(
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user",   "content": content},
                ],
                max_tokens=900,
            )
            cleaned = rc.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("```")[1]
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]
                cleaned = cleaned.strip()
            return json.loads(cleaned)

        try:
            result = _call_and_parse(system_prompt)
            _fix_or_yes_no(result, _tl_base)
            _normalize_options(result.get("question") or {}, _tl_base)

            # Validate structural quality; retry once with correction hint
            ok, reason = self._validate_question(result.get("question") or {})
            if not ok and not result.get("done"):
                logger.warning("Question rejected (%s) — retrying with correction hint.", reason)
                correction_hint = (
                    f"\n\nCRITICAL CORRECTION REQUIRED — your previous output was rejected:\n"
                    f"Reason: {reason}\n"
                    f"Fix this violation and output a corrected JSON. The question MUST pass "
                    f"the ONE-FINDING rule. Use multiple_choice if needed.\n"
                    f"REMINDER — options must be SHORT STANDALONE LABELS (1-5 words), "
                    f"not sentence fragments or questions."
                )
                result = _call_and_parse(system_prompt + correction_hint)
                _fix_or_yes_no(result, _tl_base)
                _normalize_options(result.get("question") or {}, _tl_base)

            # Normalise question_en — server route relies on this field
            q_obj = result.get("question") or {}
            if q_obj and not q_obj.get("question_en"):
                q_obj["question_en"] = q_obj.get("question", "")

            logger.info(
                "generate_next_question: done=%s type=%s dim='%s' lang=%s q='%s'",
                result.get("done"),
                q_obj.get("type", "-"),
                q_obj.get("tested_dimension", "-"),
                target_language or "en",
                str(q_obj.get("question_en", q_obj.get("question", "")))[:80],
            )
            return result

        except json.JSONDecodeError as exc:
            logger.error("generate_next_question: JSON parse error: %s", exc)
        except Exception as exc:
            logger.error("generate_next_question: API error: %s", exc, exc_info=True)

        q_text = _fallback_questions[n_asked % len(_fallback_questions)]
        return {
            "done": n_asked >= budget["max"],
            "question": {
                "question": q_text,
                "type": "yes_no",
                "options": ["Yes", "No"],
                "clinical_rationale": "fallback — API/parse error",
                "tested_dimension": None,
                "tests_history_concern": None,
            },
        }

    def generate_questions(
        self,
        chief_complaint: str,
        previous_answers: Optional[list[dict]] = None,
        demographics: Optional[dict] = None,
    ) -> list[dict]:
        """Generate follow-up triage questions based on the complaint.

        AI-102 (Agentic AI): The AI dynamically decides what to ask next
        based on (a) the initial complaint, (b) retrieved medical
        guidelines, (c) patient demographics, and (d) any previous answers.

        Demographics (age range, biological sex) are injected into the prompt
        so the model can adapt questions to the patient profile — e.g. cardiac
        risk questions are prioritised for males over 45.

        Args:
            chief_complaint: Patient's initial complaint in English.
            previous_answers: List of dicts with question/answer pairs.
            demographics: Dict with 'age_range' and 'sex' keys (from intake).

        Returns:
            List of question dicts with keys: question, type, options.
            Types: 'yes_no', 'scale', 'multiple_choice', 'free_text'.
        """
        # Retrieve relevant medical guidelines (RAG)
        context, rag_found, rag_sources = self._retrieve_context(chief_complaint)

        # Build demographic context string
        demo_context = ""
        if demographics:
            age   = demographics.get("age_range", "unknown")
            sex   = demographics.get("sex", "unknown")
            demo_context = f"\nPATIENT DEMOGRAPHICS: Age range: {age} | Biological sex: {sex}"
            logger.info("Generating questions with demographics: age=%s sex=%s", age, sex)

        # Build previous answers context
        answers_context = ""
        if previous_answers:
            answers_context = "\nPrevious patient answers:\n"
            for ans in previous_answers:
                answers_context += f"- Q: {ans.get('question', '')} ->A: {ans.get('answer', '')}\n"

        # AI-102: Adapt system prompt based on RAG availability
        if rag_found:
            knowledge_section = f"""MEDICAL GUIDELINES (base your questions on these):
{context}

Base all questions on the guidelines above."""
        else:
            knowledge_section = """KNOWLEDGE SOURCE: General medical knowledge (no specific protocol found in knowledge base).
Use evidence-based clinical assessment principles for this complaint."""

        system_prompt = f"""You are an emergency medical triage AI assistant generating follow-up questions for a SPECIFIC patient complaint.

{knowledge_section}

════ PRIMARY DIRECTIVE ════
The complaint is: {chief_complaint}
Every single question MUST be about THIS specific complaint. If the complaint is "chest pain" — ask about radiation, diaphoresis, and STEMI history. If it's "headache" — ask about thunderclap onset, visual aura, neck stiffness. If it's "leg swelling" — ask about DVT risk, calf tenderness, recent travel. NEVER default to generic emergency questions.

RULES:
1. Generate EXACTLY 5 questions that ONLY make clinical sense for "{chief_complaint}" — not for any other complaint.
   - Question 1: The single most important red-flag ruling question for THIS complaint (worst-case rule-out).
   - Question 2: Character/quality of the main symptom specific to this presentation.
   - Question 3: Onset, timing, or trigger SPECIFIC to this complaint.
   - Question 4: Associated symptom that is diagnostically significant for THIS complaint.
   - Question 5: Medical background relevant ONLY to THIS complaint (e.g., cardiac history for chest pain, migraine history for headache, DVT history for leg pain).
2. Adapt to patient demographics: {demo_context or "unknown"}
   - Males 45+: prioritise cardiac red flags
   - Females 18-44: gynaecological causes for pelvic/abdominal pain
   - Under 18: paediatric presentations
   - 75+: falls, atypical presentations, polypharmacy
3. FORBIDDEN generic questions — NEVER ask these regardless of complaint:
   - "When did your symptoms start?" (too generic — ask onset SPECIFIC to the complaint)
   - "Do you have any other symptoms?" (too vague)
   - "Do you have any serious medical conditions?" (unless directly relevant)
   - "Are you on any medications?" (too generic)
   - "Rate your pain 1-10" (only allowed if pain is the PRIMARY complaint)
   - Any question that could apply to ANY patient regardless of complaint
4. Each question must be clinically meaningful — a doctor would need this answer to triage THIS complaint.
5. Keep questions simple — patient may be in distress. Maximum 15 words per question.
6. Do NOT ask age, sex, or anything already answered. Do NOT repeat previous answers.

CRITICAL OUTPUT RULES — MUST FOLLOW:
- NEVER use type "free_text". The patient cannot type — they are in distress.
- Every single question MUST have a non-empty "options" list with 2-6 clickable choices.
- For time questions use options like: ["Just now", "Less than 1 hour", "1-6 hours", "6-24 hours", "More than 1 day"]
- For onset questions use: ["Suddenly", "Gradually over minutes", "Gradually over hours", "Gradually over days"]
- For location questions use specific anatomical options.
- For severity always use scale type with options ["1","2","3","4","5","6","7","8","9","10"].
- Allowed types: "yes_no", "scale", "multiple_choice" ONLY.
- When a question uses "or" to connect two things (e.g. "Is X or Y?"), the two options MUST be meaningfully DIFFERENT from each other. Never connect synonyms or near-synonyms with "or".
- For "Do you have any of these conditions?" or "Do you have any allergies?" questions, add "allow_multi": true to allow patients to select multiple options.
- Questions about health conditions/medications/allergies should ALWAYS include "allow_multi": true and must include a "None of the above" option.

OUTPUT FORMAT (strict JSON):
{{
  "questions": [
    {{
      "question": "Does the pain radiate to your arm, jaw, or back?",
      "type": "yes_no",
      "options": ["Yes", "No"],
      "clinical_rationale": "Assessing for cardiac radiation pattern"
    }},
    {{
      "question": "Rate your pain on a scale of 1-10",
      "type": "scale",
      "options": ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10"],
      "clinical_rationale": "Pain severity assessment"
    }},
    {{
      "question": "When did the pain start?",
      "type": "multiple_choice",
      "options": ["Just now", "Less than 1 hour ago", "1-6 hours ago", "6-24 hours ago", "More than 1 day ago"],
      "clinical_rationale": "Onset timing for urgency assessment"
    }},
    {{
      "question": "Do you have any of these symptoms?",
      "type": "multiple_choice",
      "options": ["Sweating", "Shortness of breath", "Nausea", "Dizziness", "None"],
      "clinical_rationale": "Checking for associated cardiac symptoms"
    }}
  ]
}}
"""

        user_message = (
            f"Chief complaint: {chief_complaint}"
            f"{demo_context}"
            f"{answers_context}"
            f"\n\nGenerate condition-specific triage assessment questions."
        )

        if not self._initialized:
            return self._mock_questions(chief_complaint)

        try:
            response_content = self._chat_complete(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                max_tokens=1000,
            )

            # Robust JSON extraction: handle models that wrap JSON in prose
            if response_content:
                raw = response_content.strip()
                # If not starting with '{', find the first '{' and last '}'
                if not raw.startswith("{"):
                    start = raw.find("{")
                    end = raw.rfind("}") + 1
                    if start != -1 and end > start:
                        raw = raw[start:end]
                        logger.info("Extracted JSON from prose response for: %s", chief_complaint[:50])
                try:
                    result = json.loads(raw)
                except json.JSONDecodeError:
                    logger.warning("JSON parse failed for questions (complaint=%s) — raw snippet: %s", chief_complaint[:40], raw[:200])
                    return self._mock_questions(chief_complaint)
            else:
                return self._mock_questions(chief_complaint)

            questions = result.get("questions", [])
            if not questions:
                logger.warning("AI returned 0 questions for '%s' — using mock", chief_complaint[:50])
                return self._mock_questions(chief_complaint)

            logger.info(
                "AI generated %d questions for: %s (RAG sources: %s)",
                len(questions), chief_complaint[:50], rag_sources,
            )
            # Post-process: fix OR questions that slipped through as yes_no,
            # then attach RAG citation metadata for UI display
            for q in questions:
                _fix_or_question(q)
                q["rag_sources"] = rag_sources
            return questions

        except Exception as exc:
            logger.error("Question generation error (complaint=%s): %s", chief_complaint[:40], exc)
            return self._mock_questions(chief_complaint)

    # ------------------------------------------------------------------
    # Triage assessment
    # ------------------------------------------------------------------

    def assess_triage(
        self,
        chief_complaint: str,
        answers: list[dict],
        medical_history: Optional[dict] = None,
        language: str = "en-US",
    ) -> dict:
        """Perform final triage assessment based on all collected information.

        AI-102 (RAG + Generative AI): Combines retrieved medical guidelines
        with patient answers to produce a grounded triage classification.
        The model must cite which guidelines informed its decision.

        Args:
            chief_complaint: Patient's initial complaint in English.
            answers: All question/answer pairs collected.
            medical_history: Optional dict containing diagnoses, medications, etc.

        Returns:
            Assessment dict with triage_level, assessment, patient_summary, clinical_report, etc.
        """
        context, rag_found, rag_sources = self._retrieve_context(chief_complaint)

        answers_text = ""
        for ans in answers:
            q = ans.get('question', '')
            a = ans.get('answer', '')
            if ans.get('image'):
                answers_text += f"Q: {q} ->A: [User provided an image]\n"
            else:
                answers_text += f"Q: {q} ->A: {a}\n"

        # Use the full rich formatter (same as generate_next_question) so the
        # clinical report has access to vitals, recent doctor notes, and allergies —
        # not just a flat list of diagnosis/medication names.
        history_context = self._format_medical_history(medical_history)

        if rag_found:
            knowledge_section = f"""MEDICAL GUIDELINES (base your assessment on these):
{context}

You MUST cite the guideline sources used in source_guidelines."""
        else:
            knowledge_section = """KNOWLEDGE SOURCE: General medical knowledge (no specific protocol found in knowledge base).
Use evidence-based clinical principles. Set source_guidelines to an empty list []."""

        # Build a concise history risk-factor block to front-load the clinical report prompt
        history_risk_note = ""
        if medical_history:
            active_diags = [
                d.get("description", "")
                for d in medical_history.get("diagnoses", [])
                if d.get("status") == "active"
            ]
            allergies = [
                f"{a.get('allergen')} ->{a.get('reaction')}"
                for a in medical_history.get("allergies", [])
            ]
            active_meds = [
                f"{m.get('name')} {m.get('dosage', '')}"
                for m in medical_history.get("medications", [])
                if m.get("status") == "active"
            ]
            history_risk_note = (
                f"KNOWN ACTIVE CONDITIONS: {', '.join(active_diags) or 'none'}\n"
                f"CURRENT MEDICATIONS: {', '.join(active_meds) or 'none'}\n"
                f"ALLERGIES: {', '.join(allergies) or 'none'}\n"
                "The clinical report MUST explicitly reason about how these pre-existing "
                "factors raise or lower the probability of each suspected condition."
            )

        system_prompt = f"""You are AIVoN, a clinical triage AI supporting emergency medicine physicians.
Analyse the patient data and produce a structured triage assessment.

{knowledge_section}

{history_risk_note}

Evaluation guidance:
- Identify red flags, cross-referencing with the patient's known conditions and medications.
- Classify urgency: EMERGENCY, URGENT, or ROUTINE.
- Summarise the assessment in 2-3 clinical sentences.
- Recommend a specific action tailored to this patient's medical background.
- Write a patient-facing summary (field: patient_summary) in {language}. Use a calm, empathetic tone. Acknowledge relevant health history. Ask if the patient wants help finding the best hospital by ER capacity and traffic, and note that arrival time and a clinical summary will be shared with the hospital in advance.
- Write the SAME patient-facing summary in English (field: patient_summary_en). Identical content to patient_summary but always in English regardless of the patient's language.
- Write a doctor-facing clinical report (field: clinical_report) in English. Use formal medical terminology. Synthesise how pre-existing conditions and medications interact with the current complaint. Include ICD-10 suggestions, note allergy risks, and cite any guidelines used.

Output valid JSON with these fields: triage_level (EMERGENCY/URGENT/ROUTINE), assessment, patient_summary, patient_summary_en, clinical_report, red_flags (array), recommended_action, risk_score (1-10), source_guidelines (array), suspected_conditions (array with ICD-10 codes), time_sensitivity.
"""

        has_images = any(ans.get("image") for ans in answers)

        user_text = (
            f"Patient complaint: {chief_complaint}\n\n"
            f"Medical history:\n{history_context}\n\n"
            f"Assessment answers:\n{answers_text}"
        )

        if has_images:
            content: list[dict] = [{"type": "text", "text": user_text}]
            for ans in answers:
                if ans.get("image"):
                    b64 = ans["image"]
                    if not b64.startswith("data:image"):
                        b64 = f"data:image/jpeg;base64,{b64}"
                    content.append({"type": "image_url", "image_url": {"url": b64}})
        else:
            content = user_text

        if not self._initialized:
            mock_data = self._mock_assessment(chief_complaint, answers)
            mock_data["patient_summary"] = "We have reviewed your symptoms and recommend you to visit the hospital for further evaluation. Please do not panic, this is standard protocol."
            mock_data["clinical_report"] = f"Patient presents with {chief_complaint}. Routine mock evaluation."
            return mock_data

        try:
            response_content = self._chat_complete(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": content},
                ],
                max_tokens=2000,
            )

            # Strip markdown fences (same defensive parse as generate_next_question)
            cleaned = response_content.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("```")[1]
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]
                cleaned = cleaned.strip()

            assessment = json.loads(cleaned)

            # Validate triage level
            if assessment.get("triage_level") not in (
                TRIAGE_EMERGENCY,
                TRIAGE_URGENT,
                TRIAGE_ROUTINE,
            ):
                assessment["triage_level"] = TRIAGE_URGENT

            # Attach RAG citation metadata for display in the UI
            if rag_sources and not assessment.get("source_guidelines"):
                assessment["source_guidelines"] = rag_sources

            logger.info(
                "Triage assessment: %s (risk=%s) for '%s'. RAG sources: %s",
                assessment.get("triage_level"),
                assessment.get("risk_score"),
                chief_complaint[:50],
                rag_sources,
            )
            return assessment

        except json.JSONDecodeError as exc:
            logger.error(
                "assess_triage: JSON parse error — raw=%r — %s",
                response_content if "response_content" in dir() else "<no response>",
                exc,
            )
        except Exception as exc:
            logger.error("assess_triage: API error: %s", exc, exc_info=True)

        mock_data = self._mock_assessment(chief_complaint, answers)
        mock_data["patient_summary"] = "We have reviewed your symptoms and recommend you to visit the hospital for further evaluation. Please do not panic, this is standard protocol."
        mock_data["clinical_report"] = f"Patient presents with {chief_complaint}. Routine mock evaluation."
        return mock_data

    # ------------------------------------------------------------------
    # Patient record creation
    # ------------------------------------------------------------------

    def generate_pre_arrival_advice(
        self,
        chief_complaint: str,
        assessment: dict,
        language: str = "en-US",
    ) -> dict:
        """Generate DO / DON'T advice for the patient before arriving at hospital.

        AI-102 (Generative AI + RAG hybrid): Uses the triage assessment and
        a RAG context lookup to produce personalised pre-arrival guidance.
        When RAG has no relevant protocol, falls back to GPT-4 general
        medical knowledge. Results are translated into the patient's language.

        Args:
            chief_complaint: Patient's complaint in English.
            assessment: Full triage assessment dict from assess_triage().
            language: BCP-47 locale for translation (e.g. "de-DE").

        Returns:
            Dict with keys:
                do_list   — list[str]: actions the patient SHOULD take
                dont_list — list[str]: actions the patient MUST AVOID
                rag_sourced — bool: True if advice is grounded in guidelines
        """
        triage_level = assessment.get("triage_level", TRIAGE_URGENT)
        red_flags    = [str(f) for f in assessment.get("red_flags", [])]
        suspected    = [
            s if isinstance(s, str) else s.get("name", str(s))
            for s in assessment.get("suspected_conditions", [])
        ]

        # ── Step 1: Try RAG for condition-specific protocol ───────────────
        context, rag_found, _sources = self._retrieve_context(chief_complaint)

        if rag_found:
            knowledge_section = f"""Use the following medical guidelines to generate advice:
{context}"""
        else:
            knowledge_section = "Use general evidence-based medical knowledge to generate advice."

        # ── Step 2: Build GPT-4 prompt ────────────────────────────────────
        system_prompt = f"""You are an emergency medical triage AI providing pre-arrival
instructions to a patient who is about to travel to hospital.

{knowledge_section}

PATIENT CONTEXT:
- Triage level: {triage_level}
- Chief complaint: {chief_complaint}
- Red flags identified: {", ".join(red_flags) if red_flags else "none"}
- Suspected conditions: {", ".join(suspected) if suspected else "unknown"}

TASK: Generate practical DO and DON'T instructions for the patient to follow
RIGHT NOW, before they arrive at the hospital.

RULES:
1. DO list: 3-5 concrete actions the patient or bystander should take immediately.
2. DON'T list: 3-5 things the patient must NOT do before arrival.
3. Keep each item to ONE short sentence — the patient may be in distress.
4. Be specific to the condition (e.g. aspirin for cardiac, no food for surgical).
5. Include a caregiver action if EMERGENCY level.
6. Do NOT include "call emergency services" — that is already shown separately.

OUTPUT FORMAT (strict JSON, no extra text):
{{
  "do_list": [
    "Sit upright and rest — do not walk around",
    "Take 300mg aspirin now if not allergic and no prior dose taken",
    "Loosen any tight clothing around chest and neck",
    "Have someone stay with you at all times"
  ],
  "dont_list": [
    "Do not eat or drink anything",
    "Do not take any other medications without medical advice",
    "Do not drive yourself to hospital"
  ]
}}"""

        user_message = f"Generate pre-arrival advice for: {chief_complaint}"

        # ── Step 3: Call GPT-4 or use mock ───────────────────────────────
        if not self._initialized:
            advice = self._mock_pre_arrival_advice(chief_complaint, triage_level)
        else:
            try:
                response_content = self._chat_complete(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user",   "content": user_message},
                    ],
                    max_tokens=600,
                )
                cleaned_adv = response_content.strip()
                if cleaned_adv.startswith("```"):
                    cleaned_adv = cleaned_adv.split("```")[1]
                    if cleaned_adv.startswith("json"):
                        cleaned_adv = cleaned_adv[4:]
                    cleaned_adv = cleaned_adv.strip()
                advice = json.loads(cleaned_adv)
            except Exception as exc:
                logger.error("Pre-arrival advice generation failed: %s", exc)
                advice = self._mock_pre_arrival_advice(chief_complaint, triage_level)

        do_list   = advice.get("do_list",   [])
        dont_list = advice.get("dont_list", [])

        # ── Step 4: Translate into patient's language ─────────────────────
        if self.translator and not language.startswith("en"):
            try:
                translated_do   = [self.translator.translate_from_english(item, language) for item in do_list]
                translated_dont = [self.translator.translate_from_english(item, language) for item in dont_list]
                do_list   = translated_do
                dont_list = translated_dont
                logger.info("Pre-arrival advice translated to %s.", language)
            except Exception as exc:
                logger.warning("Advice translation failed (%s) — returning English.", exc)

        logger.info(
            "Pre-arrival advice generated: %d DO items, %d DON'T items (rag=%s, lang=%s).",
            len(do_list), len(dont_list), rag_found, language,
        )

        return {
            "do_list":     do_list,
            "dont_list":   dont_list,
            "rag_sourced": rag_found,
        }

    def _mock_pre_arrival_advice(self, chief_complaint: str, triage_level: str) -> dict:
        """Fallback pre-arrival advice when Azure OpenAI is unavailable.

        Covers the most common emergency presentations with evidence-based
        DO / DON'T lists based on standard first-aid protocols.
        """
        complaint_lower = chief_complaint.lower()

        # ── Cardiac / chest pain ──────────────────────────────────────────
        if any(kw in complaint_lower for kw in ["chest", "heart", "cardiac", "palpitat"]):
            return {
                "do_list": [
                    "Sit upright and rest — do not walk around",
                    "Take 300mg aspirin now if you are not allergic and have not already taken one",
                    "Loosen any tight clothing around chest and neck",
                    "Have someone stay with you at all times",
                    "Unlock the front door so paramedics can enter quickly",
                ],
                "dont_list": [
                    "Do not eat or drink anything",
                    "Do not take any other heart medications without medical advice",
                    "Do not drive yourself to hospital",
                    "Do not lie flat — stay seated upright",
                ],
            }

        # ── Stroke / neurological ─────────────────────────────────────────
        if any(kw in complaint_lower for kw in ["stroke", "face", "slur", "speech", "arm weakness", "sudden weakness"]):
            return {
                "do_list": [
                    "Lie the patient down with head and shoulders slightly raised",
                    "Stay calm and reassure the patient — stress worsens stroke",
                    "Note the exact time symptoms started — doctors need this",
                    "Keep the patient warm and comfortable",
                    "Unlock the front door so paramedics can enter quickly",
                ],
                "dont_list": [
                    "Do not give the patient food, water, or any medications",
                    "Do not leave the patient alone",
                    "Do not let the patient drive or walk unassisted",
                    "Do not give aspirin — it can be harmful for certain stroke types",
                ],
            }

        # ── Breathing difficulty ──────────────────────────────────────────
        if any(kw in complaint_lower for kw in ["breath", "asthma", "wheez", "inhaler", "lung"]):
            return {
                "do_list": [
                    "Sit upright — leaning slightly forward helps breathing",
                    "Use your rescue inhaler (e.g. salbutamol) if prescribed",
                    "Loosen any tight clothing around chest and neck",
                    "Open a window for fresh air if possible",
                ],
                "dont_list": [
                    "Do not lie down — this makes breathing harder",
                    "Do not smoke or stay near smoky environments",
                    "Do not exert yourself or walk quickly",
                    "Do not take extra doses of inhaler beyond what is prescribed",
                ],
            }

        # ── Diabetic emergency ────────────────────────────────────────────
        if any(kw in complaint_lower for kw in ["diabet", "sugar", "insulin", "glucose", "hypoglycemi"]):
            return {
                "do_list": [
                    "Check blood glucose immediately if a meter is available",
                    "If conscious and able to swallow, give 15g fast-acting sugar (juice, glucose tablets)",
                    "Sit or lie down in a safe position",
                    "Recheck blood sugar after 15 minutes",
                ],
                "dont_list": [
                    "Do not give food or drink if the patient is unconscious or confused",
                    "Do not inject more insulin — low blood sugar is most likely",
                    "Do not leave the patient alone",
                ],
            }

        # ── Abdominal pain ────────────────────────────────────────────────
        if any(kw in complaint_lower for kw in ["stomach", "abdom", "belly", "vomit", "nausea", "appendix"]):
            return {
                "do_list": [
                    "Lie in a comfortable position — knees slightly bent often helps",
                    "Keep a bowl nearby in case of vomiting",
                    "Note when symptoms started and whether they are getting worse",
                ],
                "dont_list": [
                    "Do not eat or drink anything — surgery may be needed",
                    "Do not take painkillers — they can mask important symptoms",
                    "Do not apply heat to the abdomen",
                ],
            }

        # ── Trauma / injury / fall ────────────────────────────────────────
        if any(kw in complaint_lower for kw in ["broken", "fracture", "fall", "trauma", "injury", "wound", "bleed"]):
            return {
                "do_list": [
                    "Keep the injured area still and supported",
                    "Apply gentle pressure to any bleeding wound with a clean cloth",
                    "Elevate the injured limb above heart level if possible",
                    "Apply ice wrapped in a cloth to reduce swelling",
                ],
                "dont_list": [
                    "Do not try to straighten or move a suspected broken bone",
                    "Do not remove an embedded object from a wound",
                    "Do not eat or drink if surgery may be needed",
                ],
            }

        # ── Generic fallback ──────────────────────────────────────────────
        if triage_level == TRIAGE_EMERGENCY:
            return {
                "do_list": [
                    "Stay as calm as possible and rest",
                    "Have someone stay with you at all times",
                    "Unlock the front door so paramedics can enter",
                    "Gather any medications you take regularly to show the doctor",
                ],
                "dont_list": [
                    "Do not eat or drink anything until assessed by a doctor",
                    "Do not drive yourself to hospital",
                    "Do not take new medications without medical advice",
                ],
            }

        return {
            "do_list": [
                "Rest and avoid strenuous activity",
                "Gather your medications and medical history documents",
                "Have someone accompany you to hospital if possible",
            ],
            "dont_list": [
                "Do not ignore worsening symptoms — return here immediately",
                "Do not self-medicate beyond what is already prescribed",
            ],
        }

    def generate_hospital_prep(
        self,
        chief_complaint: str,
        assessment: dict,
    ) -> list[str]:
        """Generate a dynamic hospital pre-arrival preparation checklist.

        AI-102 (Generative AI + RAG): Uses patient assessment and RAG context
        to produce a condition-specific list of actions for ER staff to prepare
        before the patient arrives. Replaces the static PRE_ARRIVAL_PREP dict
        in hospital_dashboard.py with GPT-4-generated, complaint-aware items.

        Args:
            chief_complaint: Patient complaint in English.
            assessment: Full triage assessment dict.

        Returns:
            List of preparation action strings for ER staff (English).
        """
        triage_level    = assessment.get("triage_level", TRIAGE_URGENT)
        red_flags       = assessment.get("red_flags", [])
        suspected       = assessment.get("suspected_conditions", [])
        risk_score      = assessment.get("risk_score", 5)
        time_sensitivity = assessment.get("time_sensitivity", "")

        context, rag_found, _sources = self._retrieve_context(chief_complaint)

        if rag_found:
            knowledge_section = f"""Use the following medical guidelines:
{context}"""
        else:
            knowledge_section = "Use general emergency medicine knowledge."

        system_prompt = f"""You are an emergency department AI assistant generating a
pre-arrival preparation checklist for ER nursing and medical staff.

{knowledge_section}

INCOMING PATIENT:
- Triage level: {triage_level}
- Chief complaint: {chief_complaint}
- Risk score: {risk_score}/10
- Time sensitivity: {time_sensitivity}
- Red flags: {", ".join(red_flags) if red_flags else "none"}
- Suspected conditions: {", ".join(suspected) if suspected else "unknown"}

TASK: Generate 4-7 specific, actionable preparation steps for ER staff to complete
BEFORE the patient arrives. Steps must be tailored to this exact presentation.

RULES:
1. Be specific to the complaint — not generic.
2. Include room/bay assignment, equipment, medications to prepare, team to alert.
3. For EMERGENCY: include trauma/resus bay, attending alert, crash cart if relevant.
4. Order steps by priority (most critical first).
5. Each item: one short imperative sentence (max 12 words).
6. Do NOT include "call ambulance" or patient-side actions.

OUTPUT FORMAT (strict JSON):
{{
  "prep_items": [
    "Activate resuscitation bay 1",
    "Alert cardiology and attending physician immediately",
    "Prepare 12-lead ECG and defibrillator",
    "Pre-order STAT troponin, BNP, and CBC",
    "Draw up aspirin 300mg and IV morphine"
  ]
}}"""

        user_message = f"Generate ER prep checklist for: {chief_complaint}"

        if not self._initialized:
            return self._mock_hospital_prep(triage_level, chief_complaint)

        try:
            response_content = self._chat_complete(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_message},
                ],
                max_tokens=400,
            )
            usage = getattr(response, "usage", None)
            if usage:
                logger.info(
                    "generate_hospital_prep — tokens: prompt=%d completion=%d total=%d",
                    usage.prompt_tokens, usage.completion_tokens, usage.total_tokens,
                )
            result = json.loads(response_content)
            items = result.get("prep_items", [])
            logger.info("Generated %d hospital prep items for '%s'", len(items), chief_complaint[:50])
            return items
        except Exception as exc:
            logger.error("Hospital prep generation failed: %s", exc)
            return self._mock_hospital_prep(triage_level, chief_complaint)

    def _mock_hospital_prep(self, triage_level: str, chief_complaint: str) -> list[str]:
        """Fallback hospital prep checklist when Azure OpenAI is unavailable."""
        complaint_lower = chief_complaint.lower()

        if any(kw in complaint_lower for kw in ["chest", "heart", "cardiac"]):
            return [
                "Activate resuscitation bay",
                "Alert cardiologist and attending physician",
                "Prepare 12-lead ECG and defibrillator",
                "Pre-order STAT troponin, BNP, CBC, and coagulation panel",
                "Draw up aspirin 300mg and IV access x2",
                "Prepare cath lab on standby",
            ]
        if any(kw in complaint_lower for kw in ["stroke", "speech", "arm weakness", "face"]):
            return [
                "Activate stroke protocol — alert neurology",
                "Reserve CT scanner for immediate head CT",
                "Prepare thrombolysis assessment checklist",
                "IV access x2 and STAT glucose check",
                "Alert stroke team and neurosurgery if haemorrhagic suspected",
            ]
        if any(kw in complaint_lower for kw in ["bleed", "trauma", "amputat", "fracture", "accident"]):
            return [
                "Activate trauma bay",
                "Alert trauma surgeon and anaesthesiology",
                "Prepare massive transfusion protocol (MTP)",
                "Type and crossmatch — order O-negative blood on standby",
                "Prepare tourniquet, surgical tray, and wound packing supplies",
                "Alert operating theatre for possible emergency surgery",
            ]
        if any(kw in complaint_lower for kw in ["breath", "asthma", "respiratory"]):
            return [
                "Prepare resuscitation room with oxygen and nebuliser",
                "Alert respiratory team",
                "Prepare salbutamol nebuliser and IV hydrocortisone",
                "STAT ABG and chest X-ray on arrival",
                "Intubation tray on standby",
            ]

        # Generic by level
        if triage_level == TRIAGE_EMERGENCY:
            return [
                "Assign resuscitation bay",
                "Alert attending physician immediately",
                "Prepare crash cart and defibrillator",
                "Pre-order STAT labs and imaging",
                "IV access x2 on arrival",
            ]
        if triage_level == TRIAGE_URGENT:
            return [
                "Assign treatment room",
                "Notify triage nurse and attending",
                "Prepare standard labs and vitals station",
                "Queue imaging as required",
            ]
        return [
            "Assign waiting area with monitoring",
            "Standard intake forms ready",
            "Vitals check on arrival",
        ]

    def create_patient_record(
        self,
        chief_complaint: str,
        assessment: dict,
        language: str = "en-US",
        eta_minutes: Optional[int] = None,
        location: Optional[dict] = None,
        demographics: Optional[dict] = None,
    ) -> dict:
        """Create a complete patient record for hospital notification.

        Args:
            chief_complaint: Patient's complaint in English.
            assessment: Triage assessment dict from assess_triage().
            language: Patient's detected language locale.
            eta_minutes: Estimated time of arrival in minutes.
            location: Patient's GPS coordinates dict.
            demographics: Age range and biological sex from intake.

        Returns:
            Complete patient notification record.
        """
        now = datetime.now(timezone.utc)
        patient_id = f"ER-{now.strftime('%Y')}-{uuid4().hex[:4].upper()}"

        record = {
            "patient_id": patient_id,
            "timestamp": now.isoformat(),
            "triage_level": assessment.get("triage_level", TRIAGE_URGENT),
            "chief_complaint": chief_complaint,
            "red_flags": assessment.get("red_flags", []),
            "assessment": assessment.get("assessment", ""),
            "suspected_conditions": assessment.get("suspected_conditions", []),
            "risk_score": assessment.get("risk_score", 5),
            "recommended_action": assessment.get("recommended_action", ""),
            "time_sensitivity": assessment.get("time_sensitivity", ""),
            "source_guidelines": assessment.get("source_guidelines", []),
            "eta_minutes": eta_minutes,
            "arrival_time": None,
            "location": location,
            "language": language,
            # Demographics — collected during intake, sent to hospital dashboard
            "age_range": demographics.get("age_range", "Unknown") if demographics else "Unknown",
            "sex": demographics.get("sex", "Unknown") if demographics else "Unknown",
        }

        if eta_minutes is not None:
            from datetime import timedelta

            arrival = now + timedelta(minutes=eta_minutes)
            record["arrival_time"] = arrival.isoformat()

        logger.info("Patient record created: %s", patient_id)
        return record

    # ------------------------------------------------------------------
    # Mock/fallback methods for demo without Azure credentials
    # ------------------------------------------------------------------

    def _mock_questions(self, chief_complaint: str) -> list[dict]:
        """Generate mock questions when Azure OpenAI is unavailable."""
        complaint_lower = chief_complaint.lower()

        if any(kw in complaint_lower for kw in ["chest", "heart", "cardiac"]):
            return [
                {
                    "question": "Does the pain radiate to your arm, jaw, or back?",
                    "type": "yes_no",
                    "options": ["Yes", "No"],
                    "clinical_rationale": "Cardiac radiation pattern",
                },
                {
                    "question": "Rate your pain on a scale of 1-10",
                    "type": "scale",
                    "options": [str(i) for i in range(1, 11)],
                    "clinical_rationale": "Pain severity",
                },
                {
                    "question": "Do you have any of these symptoms right now?",
                    "type": "multiple_choice",
                    "allow_multi": True,
                    "options": ["Sweating", "Shortness of breath", "Nausea", "Dizziness", "None of the above"],
                    "clinical_rationale": "Associated symptoms",
                },
                {
                    "question": "Do you have any of these pre-existing conditions?",
                    "type": "multiple_choice",
                    "allow_multi": True,
                    "options": ["Heart disease", "Diabetes", "High blood pressure", "Previous heart attack or stroke", "None of the above"],
                    "clinical_rationale": "Cardiac history and risk factors",
                },
                {
                    "question": "When did this chest pain start?",
                    "type": "multiple_choice",
                    "options": ["Just now", "Less than 30 min ago", "30 min–2 hours ago", "More than 2 hours ago"],
                    "clinical_rationale": "Onset timing critical for STEMI management",
                },
            ]

        if any(kw in complaint_lower for kw in ["head", "stroke", "face", "speech"]):
            return [
                {
                    "question": "Did symptoms start suddenly?",
                    "type": "yes_no",
                    "options": ["Yes", "No"],
                    "clinical_rationale": "Sudden onset assessment",
                },
                {
                    "question": "Can you smile with both sides of your face?",
                    "type": "yes_no",
                    "options": ["Yes", "No"],
                    "clinical_rationale": "FAST - Face assessment",
                },
                {
                    "question": "Can you raise both arms equally?",
                    "type": "yes_no",
                    "options": ["Yes", "No"],
                    "clinical_rationale": "FAST - Arms assessment",
                },
                {
                    "question": "How is your speech right now?",
                    "type": "multiple_choice",
                    "options": ["Normal and clear", "Slightly slurred", "Very slurred or hard to understand", "Unable to speak"],
                    "clinical_rationale": "FAST - Speech assessment",
                },
                {
                    "question": "When did these symptoms start?",
                    "type": "multiple_choice",
                    "options": ["Within the last 30 min", "30 min–1 hour ago", "1–3 hours ago", "More than 3 hours ago"],
                    "clinical_rationale": "Thrombolysis time window assessment",
                },
            ]

        if any(kw in complaint_lower for kw in ["stomach", "abdom", "belly", "vomit", "nausea"]):
            return [
                {
                    "question": "Where exactly is the pain?",
                    "type": "multiple_choice",
                    "options": ["Upper right", "Upper left", "Lower right", "Lower left", "Central", "All over"],
                    "clinical_rationale": "Pain localization for differential diagnosis",
                },
                {
                    "question": "Rate your pain on a scale of 1-10",
                    "type": "scale",
                    "options": [str(i) for i in range(1, 11)],
                    "clinical_rationale": "Pain severity assessment",
                },
                {
                    "question": "Do you have any of these symptoms?",
                    "type": "multiple_choice",
                    "options": ["Fever", "Vomiting", "Diarrhea", "Blood in stool", "None"],
                    "clinical_rationale": "Associated GI symptoms",
                },
                {
                    "question": "Was the onset sudden or gradual?",
                    "type": "yes_no",
                    "options": ["Sudden", "Gradual"],
                    "clinical_rationale": "Onset pattern for surgical vs medical cause",
                },
                {
                    "question": "Do you have a fever or have you recently had one?",
                    "type": "yes_no",
                    "options": ["Yes, fever now", "Yes, earlier today", "No fever"],
                    "clinical_rationale": "Infectious vs non-infectious abdominal cause",
                },
            ]

        if any(kw in complaint_lower for kw in ["breath", "asthma", "wheez", "cough", "lung"]):
            return [
                {
                    "question": "Can you complete a full sentence without stopping to breathe?",
                    "type": "yes_no",
                    "options": ["Yes", "No"],
                    "clinical_rationale": "Severity of respiratory distress",
                },
                {
                    "question": "When did the breathing difficulty start?",
                    "type": "multiple_choice",
                    "options": ["Just now", "Hours ago", "Days ago", "Ongoing"],
                    "clinical_rationale": "Onset timing",
                },
                {
                    "question": "Do you have asthma, COPD, or any lung disease?",
                    "type": "yes_no",
                    "options": ["Yes", "No"],
                    "clinical_rationale": "Respiratory history",
                },
                {
                    "question": "Were you exposed to anything before this started?",
                    "type": "multiple_choice",
                    "options": ["Allergen", "Smoke/fumes", "Cold air", "Exercise", "Nothing specific"],
                    "clinical_rationale": "Trigger identification",
                },
                {
                    "question": "Do you have any bluish discoloration of your lips or fingertips?",
                    "type": "yes_no",
                    "options": ["Yes", "No"],
                    "clinical_rationale": "Cyanosis — severe hypoxia red flag",
                },
            ]

        if any(kw in complaint_lower for kw in ["back pain", "back ache", "backache", "lumbar", "spine", "lower back", "upper back", "sırt"]):
            return [
                {
                    "question": "Where exactly is the back pain?",
                    "type": "multiple_choice",
                    "options": ["Lower back (lumbar)", "Upper back", "Between shoulder blades", "One side only", "Entire back"],
                    "clinical_rationale": "Pain localization guides diagnosis (lumbar disc vs. kidney vs. spinal)",
                },
                {
                    "question": "Does the pain shoot down your leg or buttock?",
                    "type": "yes_no",
                    "options": ["Yes — shoots down leg", "No — stays in back"],
                    "clinical_rationale": "Radiculopathy / sciatica red flag",
                },
                {
                    "question": "When did this back pain start?",
                    "type": "multiple_choice",
                    "options": ["After an injury or fall", "After lifting something heavy", "Woke up with it", "Gradually over days", "Suddenly without cause"],
                    "clinical_rationale": "Mechanism of injury — trauma vs. spontaneous vs. discogenic",
                },
                {
                    "question": "Do you have numbness, tingling, or weakness in your legs?",
                    "type": "yes_no",
                    "options": ["Yes", "No"],
                    "clinical_rationale": "Cauda equina / cord compression red flag — requires urgent imaging",
                },
                {
                    "question": "Any difficulty with bladder or bowel control?",
                    "type": "yes_no",
                    "options": ["Yes", "No"],
                    "clinical_rationale": "Cauda equina syndrome emergency indicator",
                },
            ]

        if any(kw in complaint_lower for kw in ["leg pain", "leg ache", "calf", "thigh", "shin", "leg swelling", "leg cramp", "knee pain", "ankle pain", "foot pain", "bacak", "diz"]):
            return [
                {
                    "question": "Where is the pain in your leg?",
                    "type": "multiple_choice",
                    "options": ["Calf (lower leg)", "Thigh (upper leg)", "Knee", "Ankle", "Foot", "Entire leg"],
                    "clinical_rationale": "Location guides DVT, muscle, joint, or vascular assessment",
                },
                {
                    "question": "Is the leg swollen, red, or warm to touch?",
                    "type": "multiple_choice",
                    "allow_multi": True,
                    "options": ["Swollen", "Red/discolored", "Warm to touch", "None of these"],
                    "clinical_rationale": "DVT / cellulitis / thrombophlebitis red flags",
                },
                {
                    "question": "Did the pain start after an injury or fall?",
                    "type": "yes_no",
                    "options": ["Yes — after injury/fall", "No — started on its own"],
                    "clinical_rationale": "Traumatic vs. spontaneous onset — fracture vs. DVT vs. cramp",
                },
                {
                    "question": "Have you had recent surgery, long travel, or prolonged bedrest?",
                    "type": "yes_no",
                    "options": ["Yes", "No"],
                    "clinical_rationale": "DVT risk factors — immobility / post-surgical state",
                },
                {
                    "question": "Rate your leg pain on a scale of 1-10",
                    "type": "scale",
                    "options": [str(i) for i in range(1, 11)],
                    "clinical_rationale": "Pain severity to determine urgency",
                },
            ]

        if any(kw in complaint_lower for kw in ["arm pain", "shoulder pain", "wrist", "elbow", "hand pain", "finger", "arm swelling", "arm injury", "kol", "omuz"]):
            return [
                {
                    "question": "Where exactly is the arm pain?",
                    "type": "multiple_choice",
                    "options": ["Shoulder", "Upper arm", "Elbow", "Forearm", "Wrist", "Hand / fingers"],
                    "clinical_rationale": "Location narrows fracture, joint, or vascular cause",
                },
                {
                    "question": "Did it happen after a fall or direct impact?",
                    "type": "yes_no",
                    "options": ["Yes — after injury", "No — no injury"],
                    "clinical_rationale": "Traumatic fracture vs. spontaneous (thrombosis, neuropathy)",
                },
                {
                    "question": "Can you move the arm normally?",
                    "type": "multiple_choice",
                    "options": ["Full movement, no pain", "Limited movement with pain", "Barely able to move", "Cannot move at all"],
                    "clinical_rationale": "Range of motion assessment for fracture vs. soft tissue",
                },
                {
                    "question": "Is there numbness or tingling in the hand or fingers?",
                    "type": "yes_no",
                    "options": ["Yes", "No"],
                    "clinical_rationale": "Nerve compression or vascular compromise red flag",
                },
                {
                    "question": "Is the arm visibly deformed, bruised, or swollen?",
                    "type": "multiple_choice",
                    "allow_multi": True,
                    "options": ["Visibly deformed", "Swollen", "Bruised", "None of these"],
                    "clinical_rationale": "Fracture / dislocation vs. soft tissue injury",
                },
            ]

        if any(kw in complaint_lower for kw in ["fever", "temperature", "chills", "feverish", "high temp", "ateş", "ates"]):
            return [
                {
                    "question": "What is your current temperature if known?",
                    "type": "multiple_choice",
                    "options": ["Below 38°C (100.4°F)", "38–39°C (100.4–102.2°F)", "39–40°C (102.2–104°F)", "Above 40°C (104°F)", "Don't know"],
                    "clinical_rationale": "Fever severity classification for sepsis screening",
                },
                {
                    "question": "How long have you had the fever?",
                    "type": "multiple_choice",
                    "options": ["Less than 24 hours", "1–3 days", "4–7 days", "More than 1 week"],
                    "clinical_rationale": "Duration guides viral vs. bacterial vs. systemic cause",
                },
                {
                    "question": "Do you have any of these symptoms along with the fever?",
                    "type": "multiple_choice",
                    "allow_multi": True,
                    "options": ["Stiff neck", "Severe headache", "Difficulty breathing", "Skin rash", "Confusion", "None of these"],
                    "clinical_rationale": "Meningitis / sepsis red flags requiring immediate attention",
                },
                {
                    "question": "Do you have any pain or burning when urinating?",
                    "type": "yes_no",
                    "options": ["Yes", "No"],
                    "clinical_rationale": "Urinary tract infection / pyelonephritis as fever source",
                },
                {
                    "question": "Have you recently travelled abroad or been exposed to someone sick?",
                    "type": "yes_no",
                    "options": ["Yes", "No"],
                    "clinical_rationale": "Travel-related illness / infectious disease exposure",
                },
            ]

        if any(kw in complaint_lower for kw in ["dizzy", "dizziness", "vertigo", "faint", "fainting", "lightheaded", "light-headed", "pass out", "blackout", "syncope", "baş dönmesi", "bas donmesi"]):
            return [
                {
                    "question": "What did the dizziness feel like?",
                    "type": "multiple_choice",
                    "options": ["Room spinning around me (vertigo)", "Feeling like I might faint", "Unsteady / loss of balance", "Sudden brief blackout / passed out"],
                    "clinical_rationale": "Differentiates peripheral vertigo from presyncope from syncope",
                },
                {
                    "question": "When did the dizziness start?",
                    "type": "multiple_choice",
                    "options": ["Suddenly, within seconds", "Gradually over minutes", "Gradually over hours", "Comes and goes repeatedly"],
                    "clinical_rationale": "Sudden onset suggests central (stroke) vs. peripheral (BPPV) cause",
                },
                {
                    "question": "Did you lose consciousness (black out)?",
                    "type": "yes_no",
                    "options": ["Yes — I blacked out", "No — stayed conscious"],
                    "clinical_rationale": "Loss of consciousness indicates syncope — cardiac/vasovagal evaluation needed",
                },
                {
                    "question": "Do you have any of these along with dizziness?",
                    "type": "multiple_choice",
                    "allow_multi": True,
                    "options": ["Severe headache", "Double or blurred vision", "Difficulty speaking", "One-sided weakness", "Nausea/vomiting", "None of these"],
                    "clinical_rationale": "Central cause (stroke, TIA) red flags",
                },
                {
                    "question": "Did the dizziness start when you stood up quickly?",
                    "type": "yes_no",
                    "options": ["Yes — when standing up", "No — not related to position"],
                    "clinical_rationale": "Orthostatic hypotension assessment — dehydration / medication cause",
                },
            ]

        if any(kw in complaint_lower for kw in ["rash", "allerg", "hives", "itch", "swelling face", "swollen face", "swollen throat", "lip swelling", "skin reaction", "anaphylax", "alerji", "kaşıntı"]):
            return [
                {
                    "question": "Where is the rash or swelling?",
                    "type": "multiple_choice",
                    "allow_multi": True,
                    "options": ["Face / lips", "Throat / tongue", "Arms or legs", "Torso (chest/back)", "All over body", "Nowhere — no rash"],
                    "clinical_rationale": "Anaphylaxis red flag: lip/throat/tongue swelling requires immediate epinephrine",
                },
                {
                    "question": "Do you have difficulty swallowing or feel your throat closing?",
                    "type": "yes_no",
                    "options": ["Yes", "No"],
                    "clinical_rationale": "Angioedema / anaphylaxis airway threat — immediate action needed",
                },
                {
                    "question": "Did this reaction start after eating, a sting, or taking medication?",
                    "type": "multiple_choice",
                    "options": ["After eating something", "After insect sting or bite", "After taking medication", "After touching something", "No clear trigger"],
                    "clinical_rationale": "Allergen identification for treatment and avoidance",
                },
                {
                    "question": "How quickly did this reaction develop?",
                    "type": "multiple_choice",
                    "options": ["Within minutes", "Within 1 hour", "Over several hours", "Over a day or more"],
                    "clinical_rationale": "Rapid onset (<1 hour) indicates anaphylaxis risk",
                },
                {
                    "question": "Do you have shortness of breath, chest tightness, or wheezing?",
                    "type": "yes_no",
                    "options": ["Yes", "No"],
                    "clinical_rationale": "Bronchospasm — anaphylaxis respiratory involvement red flag",
                },
            ]

        if any(kw in complaint_lower for kw in ["injury", "trauma", "fell", "fall", "hit", "cut", "wound", "bleeding", "fracture", "broken", "accident", "crush", "yaralanma", "kaza", "düşme"]):
            return [
                {
                    "question": "What type of injury occurred?",
                    "type": "multiple_choice",
                    "options": ["Fall / slip", "Motor vehicle accident", "Sports injury", "Cut or laceration", "Blunt impact / blow", "Other"],
                    "clinical_rationale": "Mechanism of injury guides assessment severity",
                },
                {
                    "question": "Which body part is injured?",
                    "type": "multiple_choice",
                    "options": ["Head / face", "Neck or spine", "Chest or abdomen", "Arm or shoulder", "Leg or hip", "Multiple areas"],
                    "clinical_rationale": "Location priorities: head/spine/chest = high risk for internal injury",
                },
                {
                    "question": "Is there active bleeding?",
                    "type": "multiple_choice",
                    "options": ["Yes — heavy, uncontrolled", "Yes — light, controlled with pressure", "Minor oozing only", "No bleeding"],
                    "clinical_rationale": "Hemorrhage control priority assessment",
                },
                {
                    "question": "Did you lose consciousness after the injury?",
                    "type": "yes_no",
                    "options": ["Yes", "No"],
                    "clinical_rationale": "Loss of consciousness after head trauma = urgent CT evaluation",
                },
                {
                    "question": "Rate your pain on a scale of 1-10",
                    "type": "scale",
                    "options": [str(i) for i in range(1, 11)],
                    "clinical_rationale": "Pain severity for triage priority",
                },
            ]

        if any(kw in complaint_lower for kw in ["eye pain", "eye hurt", "vision", "blurred vision", "double vision", "red eye", "eye swelling", "can't see", "cannot see", "blind", "göz"]):
            return [
                {
                    "question": "What is the main eye problem?",
                    "type": "multiple_choice",
                    "options": ["Pain in the eye", "Blurred or lost vision", "Double vision", "Red / irritated eye", "Foreign object in eye", "Eye discharge"],
                    "clinical_rationale": "Symptom type guides acute glaucoma vs. retinal vs. infection",
                },
                {
                    "question": "Did vision changes come on suddenly?",
                    "type": "yes_no",
                    "options": ["Yes — suddenly", "No — gradually"],
                    "clinical_rationale": "Sudden vision loss = retinal artery occlusion / detachment emergency",
                },
                {
                    "question": "Is the affected eye red?",
                    "type": "yes_no",
                    "options": ["Yes", "No"],
                    "clinical_rationale": "Conjunctivitis vs. acute angle-closure glaucoma vs. uveitis",
                },
                {
                    "question": "Was there any chemical splash or injury to the eye?",
                    "type": "yes_no",
                    "options": ["Yes — chemical or object", "No — no trauma"],
                    "clinical_rationale": "Chemical burn / foreign body requires immediate irrigation",
                },
                {
                    "question": "Do you see flashing lights, floaters, or a dark curtain in your vision?",
                    "type": "yes_no",
                    "options": ["Yes", "No"],
                    "clinical_rationale": "Retinal detachment symptoms — urgent ophthalmology",
                },
            ]

        if any(kw in complaint_lower for kw in ["urinary", "urine", "burning urination", "frequent urination", "kidney", "blood in urine", "pee", "idrar", "böbrek"]):
            return [
                {
                    "question": "What is your main urinary symptom?",
                    "type": "multiple_choice",
                    "options": ["Pain or burning when urinating", "Frequent need to urinate", "Blood in urine", "Difficulty urinating / weak stream", "No urine output"],
                    "clinical_rationale": "Symptom type differentiates UTI, kidney stone, BPH, or renal failure",
                },
                {
                    "question": "Do you have pain in your lower back or flank (side)?",
                    "type": "yes_no",
                    "options": ["Yes", "No"],
                    "clinical_rationale": "Flank pain + urinary symptoms = kidney stone or pyelonephritis",
                },
                {
                    "question": "Do you have a fever above 38°C (100.4°F)?",
                    "type": "yes_no",
                    "options": ["Yes", "No"],
                    "clinical_rationale": "Fever + UTI symptoms = possible pyelonephritis requiring IV antibiotics",
                },
                {
                    "question": "How long have you had this symptom?",
                    "type": "multiple_choice",
                    "options": ["Less than 24 hours", "1–3 days", "4–7 days", "More than 1 week"],
                    "clinical_rationale": "Symptom duration guides acute vs. chronic assessment",
                },
                {
                    "question": "Have you had urinary tract infections or kidney stones before?",
                    "type": "yes_no",
                    "options": ["Yes", "No"],
                    "clinical_rationale": "Prior UTI / stone history increases recurrence risk and guides treatment",
                },
            ]

        if any(kw in complaint_lower for kw in ["neck pain", "stiff neck", "neck stiffness", "neck injury", "boyun"]):
            return [
                {
                    "question": "Can you touch your chin to your chest?",
                    "type": "multiple_choice",
                    "options": ["Yes, easily", "Yes, with difficulty", "No — neck too stiff", "Too painful to try"],
                    "clinical_rationale": "Neck stiffness (meningismus) — meningitis red flag",
                },
                {
                    "question": "Did the neck pain start after a trauma or accident?",
                    "type": "yes_no",
                    "options": ["Yes — after trauma", "No — no trauma"],
                    "clinical_rationale": "Traumatic cervical spine injury requires immobilization and imaging",
                },
                {
                    "question": "Do you have a severe headache or fever along with the neck pain?",
                    "type": "yes_no",
                    "options": ["Yes", "No"],
                    "clinical_rationale": "Neck pain + headache + fever = bacterial meningitis must be ruled out",
                },
                {
                    "question": "Do you have numbness or tingling in your arms or hands?",
                    "type": "yes_no",
                    "options": ["Yes", "No"],
                    "clinical_rationale": "Cervical radiculopathy / cord compression — nerve root compromise",
                },
                {
                    "question": "When did the neck pain start?",
                    "type": "multiple_choice",
                    "options": ["Within the last hour (sudden)", "Over the past day", "Over the past few days", "Chronic — weeks or more"],
                    "clinical_rationale": "Acute sudden onset vs. gradual for differential diagnosis",
                },
            ]

        if any(kw in complaint_lower for kw in ["diabet", "sugar", "insulin", "glucose"]):
            return [
                {
                    "question": "Do you have diabetes? What type?",
                    "type": "multiple_choice",
                    "options": ["Type 1", "Type 2", "Not sure", "No diabetes"],
                    "clinical_rationale": "Diabetes classification",
                },
                {
                    "question": "What is your blood sugar if known?",
                    "type": "multiple_choice",
                    "options": ["Below 70 mg/dL", "70-180 mg/dL", "180-300 mg/dL", "Above 300 mg/dL", "Don't know"],
                    "clinical_rationale": "Glucose level assessment",
                },
                {
                    "question": "Do you have nausea, vomiting, or abdominal pain?",
                    "type": "yes_no",
                    "options": ["Yes", "No"],
                    "clinical_rationale": "DKA symptom check",
                },
                {
                    "question": "Are you feeling confused or drowsy?",
                    "type": "yes_no",
                    "options": ["Yes", "No"],
                    "clinical_rationale": "Altered mental status assessment",
                },
                {
                    "question": "Have you taken your insulin or diabetes medication today?",
                    "type": "multiple_choice",
                    "options": ["Yes, as prescribed", "Took more than prescribed", "Missed a dose", "Don't take medication"],
                    "clinical_rationale": "Medication compliance for hypo/hyperglycaemia cause",
                },
            ]

        # Generic questions (5 questions for any complaint not matched above)
        return [
            {
                "question": "When did your symptoms start?",
                "type": "multiple_choice",
                "options": ["Just now", "Less than 1 hour ago", "1-6 hours ago", "6-24 hours ago", "More than 1 day ago"],
                "clinical_rationale": "Onset timing for urgency classification",
            },
            {
                "question": "Rate your discomfort on a scale of 1-10",
                "type": "scale",
                "options": [str(i) for i in range(1, 11)],
                "clinical_rationale": "Severity assessment",
            },
            {
                "question": "Are your symptoms getting better, worse, or staying the same?",
                "type": "multiple_choice",
                "options": ["Getting worse", "Staying the same", "Getting better"],
                "clinical_rationale": "Symptom trajectory for urgency assessment",
            },
            {
                "question": "Do you have any of these additional symptoms?",
                "type": "multiple_choice",
                "allow_multi": True,
                "options": ["High fever", "Severe pain", "Difficulty breathing", "Loss of consciousness", "None of these"],
                "clinical_rationale": "Red flag symptom screening",
            },
            {
                "question": "Do you have any serious medical conditions or allergies?",
                "type": "multiple_choice",
                "allow_multi": True,
                "options": ["Heart disease", "Diabetes", "Severe allergies", "High blood pressure", "None of the above"],
                "clinical_rationale": "Risk stratification from medical history",
            },
        ]

    def _mock_assessment(self, chief_complaint: str, answers: list[dict]) -> dict:
        """Generate mock assessment when Azure OpenAI is unavailable.

        Each answer is evaluated against the clinical intent of its OWN
        question only. Context flags (is_cardiac, is_stroke, etc.) are set
        once from the chief complaint so that keyword checks in the answer
        loop never fire for the wrong clinical protocol.

        ROOT BUG FIXED: "arm" was in the cardiac radiation keyword list,
        causing FAST stroke questions like "Can you raise both arms equally?"
        to falsely trigger pain_radiation when the answer was "Yes".
        Now cardiac radiation requires the question itself to mention
        "radiat", "jaw" or "back" — not just the word "arm".
        """
        complaint_lower = chief_complaint.lower()

        # ── Detect clinical context from chief complaint (set ONCE) ──────
        is_cardiac = any(kw in complaint_lower for kw in [
            "chest", "heart", "cardiac", "palpitat",
        ])
        is_stroke = any(kw in complaint_lower for kw in [
            "stroke", "slurred", "speech", "face droop", "arm weakness",
            "can't move", "sudden weakness", "facial",
        ])
        is_respiratory = any(kw in complaint_lower for kw in [
            "breath", "asthma", "wheez", "cough", "lung", "inhaler",
        ])
        is_abdominal = any(kw in complaint_lower for kw in [
            "stomach", "abdom", "belly", "vomit", "nausea", "appendix",
        ])
        is_diabetic = any(kw in complaint_lower for kw in [
            "diabet", "sugar", "insulin", "glucose", "hypoglycemi",
        ])

        # ── Multilingual affirmative / negative sets ──────────────────────
        # EN / DE / TR / FR / ES / IT / PT / RU / AR / ZH
        AFFIRMATIVE = {
            "yes", "ja", "evet", "oui", "sí", "si", "sì", "sim", "да", "نعم", "是",
        }
        NEGATIVE = {
            "no", "nein", "hayır", "non", "não", "нет", "لا", "否",
        }

        # ── Accumulators ─────────────────────────────────────────────────
        red_flags: list[str] = []
        positive_findings: list[str] = []
        negative_findings: list[str] = []
        severity_score = 0

        for ans in answers:
            question = ans.get("question", "").lower()
            answer   = str(ans.get("answer", "")).lower().strip()

            # ── 1. Pain scale (1-10) ─────────────────────────────────────
            if answer.isdigit():
                val = int(answer)
                if val >= 7:
                    severity_score += 3
                    positive_findings.append(f"Pain severity {val}/10")
                elif val >= 4:
                    severity_score += 1

            # ── 2. Yes/No answers — matched ONLY to their own question ───
            is_affirmative = answer in AFFIRMATIVE
            is_negative    = answer in NEGATIVE

            if is_affirmative:
                severity_score += 1

                # CARDIAC: radiation only when the question explicitly asks
                # about radiation/jaw/back — NOT when it mentions "arm raise"
                if is_cardiac and any(w in question for w in ["radiat", "jaw", "back"]):
                    red_flags.append("pain_radiation")
                    positive_findings.append("Pain radiates to arm/jaw/back")

                # CARDIAC: history
                if any(w in question for w in ["heart disease", "cardiac history", "prior heart"]):
                    red_flags.append("cardiac_history")
                    positive_findings.append("History of heart disease")

                # STROKE / FAST — sudden onset (affirmative = bad)
                if any(w in question for w in ["sudden", "suddenly", "plötzlich", "aniden"]):
                    red_flags.append("sudden_onset")
                    positive_findings.append("Sudden onset of symptoms")

                # STROKE / FAST — speech slurred (affirmative = bad)
                if any(w in question for w in ["slur", "slurred", "unclear speech"]):
                    red_flags.append("speech_impairment")
                    positive_findings.append("Speech is slurred")

                # STROKE / FAST — face symmetry (affirmative = GOOD, no red flag)
                if any(w in question for w in ["smile", "face", "symmetr", "both sides"]):
                    positive_findings.append("Facial symmetry intact")

                # STROKE / FAST — arm raise (affirmative = GOOD, no red flag)
                # FIX: "arm" alone no longer triggers cardiac pain_radiation
                if any(w in question for w in ["raise", "lift both", "arms equally"]):
                    positive_findings.append("Can raise both arms equally")

                # GENERAL
                if any(w in question for w in ["fever", "fieber", "ateş", "temperature"]):
                    red_flags.append("fever")
                    positive_findings.append("Has fever")
                if any(w in question for w in ["blood", "blut", "bleeding", "bleed"]):
                    red_flags.append("bleeding")
                    positive_findings.append("Blood present")
                if any(w in question for w in ["chronic", "condition", "medical condition"]):
                    positive_findings.append("Has chronic medical conditions")
                if any(w in question for w in ["confused", "drowsy", "unconscious", "altered"]):
                    red_flags.append("altered_mental_status")
                    positive_findings.append("Confusion or drowsiness reported")

            elif is_negative:
                # STROKE / FAST — face symmetry (negative = RED FLAG)
                if any(w in question for w in ["smile", "face", "symmetr", "both sides"]):
                    red_flags.append("facial_asymmetry")
                    positive_findings.append("Cannot smile symmetrically (facial droop)")

                # STROKE / FAST — arm raise (negative = RED FLAG)
                if any(w in question for w in ["raise", "lift both", "arms equally"]):
                    red_flags.append("arm_weakness")
                    positive_findings.append("Cannot raise both arms equally")

                # STROKE / FAST — speech slurred (negative = GOOD)
                if any(w in question for w in ["slur", "slurred", "unclear speech"]):
                    negative_findings.append("Speech is NOT slurred")

                # RESPIRATORY
                if any(w in question for w in ["sentence", "complete a", "breathe without"]):
                    red_flags.append("severe_dyspnea")
                    positive_findings.append("Cannot complete a sentence (severe dyspnea)")

                # CARDIAC history negative
                if any(w in question for w in ["heart disease", "cardiac history"]):
                    negative_findings.append("No history of heart disease")
                if any(w in question for w in ["chronic", "condition"]):
                    negative_findings.append("No chronic conditions reported")

            # ── 3. Multi-choice symptom keywords (language-aware) ────────
            if any(w in answer for w in [
                "sweating", "schwitzen", "terleme", "transpiration",
                "sudoración", "sudorazione", "suor", "потоотделение", "تعرق",
            ]):
                red_flags.append("diaphoresis")
                positive_findings.append("Sweating")

            if any(w in answer for w in [
                "shortness", "breath", "atemnot", "nefes", "essoufflement",
                "dificultad respirar", "mancanza di fiato", "falta de ar",
                "одышка", "ضيق التنفس",
            ]):
                red_flags.append("dyspnea")
                positive_findings.append("Shortness of breath")

            if any(w in answer for w in [
                "nausea", "übelkeit", "bulantı", "nausée", "náuseas",
                "náusea", "тошнота", "غثيان",
            ]):
                positive_findings.append("Nausea")

            if any(w in answer for w in [
                "dizz", "schwindel", "baş dönmesi", "vertige", "mareo",
                "vertigine", "tontura", "головокружение", "دوار",
            ]):
                red_flags.append("dizziness")
                positive_findings.append("Dizziness")

            if any(w in answer for w in [
                "vomit", "erbrechen", "kusma", "vomissement", "vómito",
                "vomito", "vômito", "рвота", "قيء",
            ]):
                positive_findings.append("Vomiting")

            if any(w in answer for w in [
                "fever", "fieber", "ateş", "fièvre", "fiebre", "febbre",
                "febre", "лихорадка", "حمى",
            ]):
                red_flags.append("fever")
                positive_findings.append("Fever")

            if any(w in answer for w in [
                "blood", "blut", "kan", "sang", "sangre", "sangue",
                "кровь", "دم",
            ]):
                red_flags.append("bleeding_sign")
                positive_findings.append("Blood reported")

            if "lower right" in answer:
                positive_findings.append("Lower right quadrant pain (possible appendicitis)")
            if "all over" in answer or "diffuse" in answer:
                red_flags.append("diffuse_pain")
                positive_findings.append("Diffuse abdominal pain")

        # ── Deduplicate while preserving order ────────────────────────────
        red_flags = list(dict.fromkeys(red_flags))

        # ── FAST stroke logic: facial_asymmetry OR arm_weakness = EMERGENCY ─
        fast_positive = "facial_asymmetry" in red_flags or "arm_weakness" in red_flags
        # Stroke with sudden onset also = EMERGENCY even if FAST negative
        stroke_emergency = is_stroke and ("sudden_onset" in red_flags or fast_positive)

        # ── Triage level ──────────────────────────────────────────────────
        emergency_complaint_kw = [
            "chest pain", "heart attack", "stroke", "unconscious",
            "can't breathe", "seizure", "arm weakness", "face droop",
            "can't move", "slurred",
        ]
        urgent_complaint_kw = [
            "pain", "fever", "vomiting", "broken", "injury",
            "fall", "cough", "stomach",
        ]

        if (
            fast_positive
            or stroke_emergency
            or len(red_flags) >= 3
            or any(kw in complaint_lower for kw in emergency_complaint_kw)
        ):
            level = TRIAGE_EMERGENCY
            risk_score = min(10, 7 + len(red_flags))
        elif (
            len(red_flags) >= 1
            or severity_score >= 3
            or any(kw in complaint_lower for kw in urgent_complaint_kw)
        ):
            level = TRIAGE_URGENT
            risk_score = min(8, 4 + len(red_flags))
        else:
            level = TRIAGE_ROUTINE
            risk_score = max(1, min(4, severity_score))

        # ── Human-readable summary ────────────────────────────────────────
        parts: list[str] = []
        if positive_findings:
            parts.append("Findings: " + "; ".join(positive_findings[:5]) + ".")
        if negative_findings:
            parts.append("Negative: " + "; ".join(negative_findings[:3]) + ".")
        if red_flags and red_flags != ["none_identified"]:
            parts.append(f"{len(red_flags)} red flag(s) identified.")
        assessment_text = (" ".join(parts) if parts else "Assessment based on reported symptoms.")
        assessment_text += f" Triage level: {level}."

        # ── Suspected conditions ──────────────────────────────────────────
        suspected: list[str] = []
        if is_cardiac:
            if "pain_radiation" in red_flags or "diaphoresis" in red_flags:
                suspected.append("Acute Coronary Syndrome")
            else:
                suspected.append("Chest Pain — requires evaluation")
        if is_stroke:
            if fast_positive:
                suspected.append("Possible Stroke (FAST positive)")
            elif "sudden_onset" in red_flags:
                suspected.append("Possible TIA / Stroke — sudden neurological onset")
            else:
                suspected.append("Neurological symptoms — requires evaluation")
        if is_abdominal:
            suspected.append("Abdominal Pain — requires evaluation")
        if is_respiratory:
            suspected.append("Respiratory Distress")
        if is_diabetic:
            suspected.append("Diabetic Emergency — requires evaluation")
        if not suspected:
            suspected.append("Requires clinical evaluation")

        return {
            "triage_level": level,
            "assessment": assessment_text,
            "red_flags": red_flags if red_flags else ["none_identified"],
            "recommended_action": {
                TRIAGE_EMERGENCY: "Proceed to nearest ER immediately. Call emergency services if unable to travel.",
                TRIAGE_URGENT: "Visit ER or urgent care within 2 hours.",
                TRIAGE_ROUTINE: "Schedule a visit with your primary care physician. Self-care as needed.",
            }[level],
            "risk_score": risk_score,
            "source_guidelines": ["local_protocol_fallback"],
            "suspected_conditions": suspected,
            "time_sensitivity": {
                TRIAGE_EMERGENCY: "Seek ER within 10 minutes",
                TRIAGE_URGENT: "Seek medical care within 2 hours",
                TRIAGE_ROUTINE: "Schedule appointment within 48 hours",
            }[level],
            "ai_mode": "mock",
        }