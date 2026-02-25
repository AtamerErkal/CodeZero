"""
Triage Engine Module
====================
Core AI-powered triage logic. Combines Azure OpenAI (GPT-4) with RAG
from the medical knowledge base to perform dynamic patient assessment
and triage classification.

AI-102 Concepts:
  - Azure OpenAI chat completions with system/user/assistant roles
  - Structured JSON output (response_format)
  - RAG: Retrieval-Augmented Generation for grounded responses
  - Agentic AI: Multi-step reasoning with dynamic question generation
  - Prompt engineering: system prompt design for medical domain
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
# Answers are injected into the GPT-4 prompt so the model can adapt questions
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
            logger.warning(
                "Azure OpenAI credentials not configured. "
                "Using mock triage engine for demo."
            )
            return

        try:
            from openai import AzureOpenAI

            # Newer openai SDK versions (≥1.50) removed the 'proxies' kwarg.
            # If the environment has HTTP_PROXY / HTTPS_PROXY set, the SDK
            # may fail.  We catch that and create the client with an explicit
            # httpx client that respects system proxy settings.
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

            self._initialized = True
            logger.info("Azure OpenAI client initialized (deployment=%s).", self.deployment)
        except Exception as exc:
            logger.error("Failed to init Azure OpenAI client: %s", exc)

    # ------------------------------------------------------------------
    # RAG: Retrieve context from knowledge base
    # ------------------------------------------------------------------

    def _retrieve_context(self, query: str) -> tuple[str, bool]:
        """Search the medical knowledge base for relevant guidelines.

        AI-102: This is the "Retrieval" step of RAG. The search query
        is derived from the patient's complaint. Results are concatenated
        and injected into the system prompt as grounding context.

        Returns a tuple (context_text, rag_found) so callers can adapt
        their prompts when the knowledge base has no relevant content.

        Args:
            query: Search query (usually the patient's chief complaint).

        Returns:
            Tuple of (guideline text, rag_found flag).
            rag_found is True only when at least one result was retrieved.
        """
        if self.knowledge_indexer is None:
            return "", False

        try:
            results = self.knowledge_indexer.search(query, top=3)
            if not results:
                logger.info("RAG: no results for query '%s' — AI will use general knowledge.", query[:60])
                return "", False

            context_parts = []
            for r in results:
                context_parts.append(
                    f"--- Source: {r.get('source', 'Unknown')} ---\n"
                    f"{r.get('content', '')}\n"
                )
            context_text = "\n".join(context_parts)
            logger.info("RAG: found %d result(s) for query '%s'.", len(results), query[:60])
            return context_text, True

        except Exception as exc:
            logger.error("RAG retrieval error: %s", exc)
            return "", False

    # ------------------------------------------------------------------
    # Dynamic question generation (Agentic AI)
    # ------------------------------------------------------------------

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
        context, rag_found = self._retrieve_context(chief_complaint)

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
                answers_context += f"- Q: {ans.get('question', '')} → A: {ans.get('answer', '')}\n"

        # AI-102: Adapt system prompt based on RAG availability
        if rag_found:
            knowledge_section = f"""MEDICAL GUIDELINES (base your questions on these):
{context}

Base all questions on the guidelines above."""
        else:
            knowledge_section = """KNOWLEDGE SOURCE: General medical knowledge (no specific protocol found in knowledge base).
Use evidence-based clinical assessment principles for this complaint."""

        system_prompt = f"""You are an emergency medical triage AI assistant. Your role is to
ask focused, condition-specific follow-up questions to assess the severity of a patient's condition.

{knowledge_section}

RULES:
1. Generate 3-5 focused follow-up questions SPECIFIC to this exact complaint.
2. Use the patient demographics to adapt questions to their risk profile.
   - Males 45+: prioritise cardiac red flags
   - Females 18-44: consider gynaecological causes for abdominal pain
   - Under 18: consider paediatric presentations and doses
   - 75+: consider falls, polypharmacy, atypical presentations
3. Questions must help determine triage level: EMERGENCY, URGENT, or ROUTINE.
4. Prioritise RED FLAG assessment questions first.
5. Keep questions simple — the patient may be in distress.
6. Do NOT ask age or sex (already collected). Do NOT repeat previous answers.
7. Questions must be SPECIFIC to the complaint — not generic.

CRITICAL OUTPUT RULES — MUST FOLLOW:
- NEVER use type "free_text". The patient cannot type — they are in distress.
- Every single question MUST have a non-empty "options" list with 2-6 clickable choices.
- For time questions use options like: ["Just now", "Less than 1 hour", "1-6 hours", "6-24 hours", "More than 1 day"]
- For onset questions use: ["Suddenly", "Gradually over minutes", "Gradually over hours", "Gradually over days"]
- For location questions use specific anatomical options.
- For severity always use scale type with options ["1","2","3","4","5","6","7","8","9","10"].
- Allowed types: "yes_no", "scale", "multiple_choice" ONLY.

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
            response = self.openai_client.chat.completions.create(
                model=self.deployment,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                response_format={"type": "json_object"},
                max_completion_tokens=1000,
            )

            result = json.loads(response.choices[0].message.content)
            questions = result.get("questions", [])

            # Grup B: Token usage tracking for cost monitoring (Instruction requirement)
            usage = getattr(response, "usage", None)
            if usage:
                logger.info(
                    "generate_questions — tokens used: prompt=%d completion=%d total=%d",
                    usage.prompt_tokens,
                    usage.completion_tokens,
                    usage.total_tokens,
                )

            logger.info(
                "Generated %d questions for: %s", len(questions), chief_complaint[:50]
            )
            return questions

        except Exception as exc:
            logger.error("Question generation error: %s", exc)
            return self._mock_questions(chief_complaint)

    # ------------------------------------------------------------------
    # Triage assessment
    # ------------------------------------------------------------------

    def assess_triage(
        self,
        chief_complaint: str,
        answers: list[dict],
    ) -> dict:
        """Perform final triage assessment based on all collected information.

        AI-102 (RAG + Generative AI): Combines retrieved medical guidelines
        with patient answers to produce a grounded triage classification.
        The model must cite which guidelines informed its decision.

        Args:
            chief_complaint: Patient's initial complaint in English.
            answers: All question/answer pairs collected.

        Returns:
            Assessment dict with triage_level, assessment, red_flags,
            recommended_action, risk_score, and source_guidelines.
        """
        context, rag_found = self._retrieve_context(chief_complaint)

        answers_text = "\n".join(
            f"Q: {a.get('question', '')} → A: {a.get('answer', '')}"
            for a in answers
        )

        # AI-102: RAG-aware prompt — cite sources when available,
        # fall back to general knowledge transparently when not.
        if rag_found:
            knowledge_section = f"""MEDICAL GUIDELINES (base your assessment on these):
{context}

You MUST cite the guideline sources used in source_guidelines."""
        else:
            knowledge_section = """KNOWLEDGE SOURCE: General medical knowledge (no specific protocol found in knowledge base).
Use evidence-based clinical principles. Set source_guidelines to an empty list []."""

        system_prompt = f"""You are an emergency medical triage AI. Analyze the patient's
symptoms and answers to determine the appropriate triage level.

{knowledge_section}

ASSESSMENT RULES:
1. Identify ALL red flags present.
2. Classify into: EMERGENCY, URGENT, or ROUTINE.
3. Provide a clear assessment summary.
4. Recommend specific actions.

OUTPUT FORMAT (strict JSON):
{{
  "triage_level": "EMERGENCY|URGENT|ROUTINE",
  "assessment": "Brief clinical assessment summary",
  "red_flags": ["list", "of", "identified", "red", "flags"],
  "recommended_action": "What the patient should do",
  "risk_score": 8,
  "source_guidelines": ["guideline sources used, or empty list if none"],
  "suspected_conditions": ["possible conditions"],
  "time_sensitivity": "How urgent (e.g., 'Seek ER within 10 minutes')"
}}
"""

        user_message = (
            f"Chief complaint: {chief_complaint}\n\n"
            f"Patient answers:\n{answers_text}\n\n"
            f"Provide triage assessment."
        )

        if not self._initialized:
            return self._mock_assessment(chief_complaint, answers)

        try:
            response = self.openai_client.chat.completions.create(
                model=self.deployment,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                response_format={"type": "json_object"},
                max_completion_tokens=1000,
            )

            assessment = json.loads(response.choices[0].message.content)

            # Grup B: Token usage tracking for cost monitoring (Instruction requirement)
            usage = getattr(response, "usage", None)
            if usage:
                logger.info(
                    "assess_triage — tokens used: prompt=%d completion=%d total=%d",
                    usage.prompt_tokens,
                    usage.completion_tokens,
                    usage.total_tokens,
                )

            # Validate triage level
            if assessment.get("triage_level") not in (
                TRIAGE_EMERGENCY,
                TRIAGE_URGENT,
                TRIAGE_ROUTINE,
            ):
                assessment["triage_level"] = TRIAGE_URGENT

            logger.info(
                "Triage assessment: %s (risk=%s) for '%s'",
                assessment.get("triage_level"),
                assessment.get("risk_score"),
                chief_complaint[:50],
            )
            return assessment

        except Exception as exc:
            logger.error("Triage assessment error: %s", exc)
            return self._mock_assessment(chief_complaint, answers)

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
        red_flags    = assessment.get("red_flags", [])
        suspected    = assessment.get("suspected_conditions", [])

        # ── Step 1: Try RAG for condition-specific protocol ───────────────
        context, rag_found = self._retrieve_context(chief_complaint)

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
                response = self.openai_client.chat.completions.create(
                    model=self.deployment,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user",   "content": user_message},
                    ],
                    response_format={"type": "json_object"},
                    max_completion_tokens=600,
                )
                usage = getattr(response, "usage", None)
                if usage:
                    logger.info(
                        "generate_pre_arrival_advice — tokens: prompt=%d completion=%d total=%d",
                        usage.prompt_tokens, usage.completion_tokens, usage.total_tokens,
                    )
                advice = json.loads(response.choices[0].message.content)
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

        context, rag_found = self._retrieve_context(chief_complaint)

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
            response = self.openai_client.chat.completions.create(
                model=self.deployment,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_message},
                ],
                response_format={"type": "json_object"},
                max_completion_tokens=400,
            )
            usage = getattr(response, "usage", None)
            if usage:
                logger.info(
                    "generate_hospital_prep — tokens: prompt=%d completion=%d total=%d",
                    usage.prompt_tokens, usage.completion_tokens, usage.total_tokens,
                )
            result = json.loads(response.choices[0].message.content)
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
                    "question": "Do you have any of these symptoms?",
                    "type": "multiple_choice",
                    "options": ["Sweating", "Shortness of breath", "Nausea", "Dizziness", "None"],
                    "clinical_rationale": "Associated symptoms",
                },
                {
                    "question": "Do you have a history of heart disease?",
                    "type": "yes_no",
                    "options": ["Yes", "No"],
                    "clinical_rationale": "Cardiac history",
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
                    "question": "Is your speech slurred or unclear?",
                    "type": "yes_no",
                    "options": ["Yes", "No"],
                    "clinical_rationale": "FAST - Speech assessment",
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
            ]

        # Generic questions
        return [
            {
                "question": "When did the symptoms start?",
                "type": "multiple_choice",
                "options": ["Just now", "Hours ago", "Days ago", "Weeks ago"],
                "clinical_rationale": "Onset timing",
            },
            {
                "question": "Rate your discomfort on a scale of 1-10",
                "type": "scale",
                "options": [str(i) for i in range(1, 11)],
                "clinical_rationale": "Severity assessment",
            },
            {
                "question": "Do you have any chronic medical conditions?",
                "type": "yes_no",
                "options": ["Yes", "No"],
                "clinical_rationale": "Medical history",
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
        }