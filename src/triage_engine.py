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
        self._init_error: str = ""
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

        # Recent Vitals
        vitals = medical_history.get("vitals", [])
        if vitals:
            v = vitals[0] # Latest vitals
            v_str = f"Latest Vitals ({v.get('recorded_at','')}): BP {v.get('bp_systolic','?')}/{v.get('bp_diastolic','?')}, HR {v.get('heart_rate','?')}, SpO2 {v.get('spo2','?')}%, Temp {v.get('temperature','?')}°C"
            parts.append(v_str)

        # Doctor Notes (Last 2)
        notes = medical_history.get("doctor_notes", [])
        if notes:
            parts.append("Recent Clinical Notes:")
            for n in notes[:2]:
                parts.append(f"- {n.get('note_date')}: {n.get('assessment')} (Plan: {n.get('plan')})")
        
        return "\n".join(parts)

    # ------------------------------------------------------------------
    # Dynamic question generation (Agentic AI)
    # ------------------------------------------------------------------

    def _build_pre_assessment_hypothesis(
        self,
        chief_complaint: str,
        medical_history: Optional[dict],
        demographics: Optional[dict],
    ) -> str:
        """Build a clinical hypothesis block that AIVoN uses before asking the first question.

        This is the core of the "think before you ask" behaviour: AIVoN synthesises the
        patient's full medical background and the current complaint into a prioritised list
        of differential diagnoses it wants to rule in or out. Every subsequent question is
        then driven by this hypothesis rather than a generic symptom checklist.

        Returns a formatted string injected into the system prompt so the model has an
        explicit internal reasoning frame when it produces the first question.
        """
        if not medical_history:
            return (
                "No prior medical history on file. "
                "Approach this as a de-novo presentation and ask broad screening questions first."
            )

        hist_str = self._format_medical_history(medical_history)

        # Build a compact demographics note
        demo_note = ""
        if demographics:
            age   = demographics.get("age_range", "")
            sex   = demographics.get("sex", "")
            if age or sex:
                demo_note = f"Patient demographics: {sex}, {age}."

        hypothesis_prompt = f"""You are a senior emergency physician conducting a rapid pre-assessment 
before starting patient questioning. You have the patient's FULL medical history and their current complaint.

{demo_note}

[FULL MEDICAL HISTORY]
{hist_str}

[CURRENT CHIEF COMPLAINT]
{chief_complaint}

TASK: In 3-5 sentences, reason through the following and produce a structured clinical hypothesis:
1. Which of the patient's known conditions are MOST LIKELY connected to the current complaint?
2. What is your PRIMARY differential diagnosis given the combination of history + complaint?
3. What are the 2-3 most dangerous conditions you MUST rule out first (red flag differentials)?
4. Which specific aspect of this patient's history (medications, allergies, past procedures) 
   should most influence your line of questioning?

Respond ONLY with a JSON object:
{{
  "primary_hypothesis": "One sentence: most likely diagnosis given history + complaint",
  "red_flag_differentials": ["condition1", "condition2", "condition3"],
  "history_risk_factors": ["most relevant risk factor from history", "..."],
  "questioning_strategy": "One sentence: how history should shape the questions asked"
}}"""

        if not self._initialized:
            return (
                f"Pre-assessment (mock): Patient has known medical history. "
                f"Current complaint: {chief_complaint}. "
                f"Proceed with targeted questioning based on risk profile."
            )

        try:
            response_content = self._chat_complete(
                messages=[
                    {"role": "user", "content": hypothesis_prompt},
                ],
                max_tokens=400,
            )
            hyp = json.loads(response_content)
            parts = [
                f"PRIMARY HYPOTHESIS: {hyp.get('primary_hypothesis', '')}",
                f"RED FLAG DIFFERENTIALS TO RULE OUT: {', '.join(hyp.get('red_flag_differentials', []))}",
                f"RELEVANT HISTORY RISK FACTORS: {', '.join(hyp.get('history_risk_factors', []))}",
                f"QUESTIONING STRATEGY: {hyp.get('questioning_strategy', '')}",
            ]
            hypothesis_text = "\n".join(parts)
            logger.info("Pre-assessment hypothesis built for complaint: %s", chief_complaint[:60])
            return hypothesis_text
        except Exception as exc:
            logger.warning("Pre-assessment hypothesis generation failed (%s) — using history summary.", exc)
            return self._format_medical_history(medical_history)

    def generate_next_question(
        self,
        chief_complaint: str,
        previous_answers: list[dict],
        demographics: Optional[dict] = None,
        medical_history: Optional[dict] = None,
    ) -> dict:
        """Generate EXACTLY ONE focused clinical follow-up question.

        On the very first call (previous_answers is empty) AIVoN builds a clinical
        pre-assessment hypothesis by cross-referencing the patient's full medical
        history with the current complaint. This hypothesis is injected into the
        system prompt so every question is driven by a targeted differential
        diagnosis strategy rather than a generic symptom checklist.

        On subsequent calls the hypothesis is rebuilt cheaply from the cached history
        string and the evolving transcript is used to avoid repetition.
        """
        if not self._initialized:
            count = len(previous_answers)
            if count >= 4:
                return {"done": True, "question": None}
            mock_qs = [
                "Are you in severe pain?",
                "Do you have a high fever?",
                "Is it difficult to breathe?",
                "Do you feel dizzy or faint?",
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

        # ── Step 1: Build or reuse clinical pre-assessment hypothesis ────────
        # On the first question (empty transcript) we run the full hypothesis LLM call.
        # On subsequent questions we reuse the cheaper formatted history string so we
        # do not burn extra tokens on every turn.
        is_first_question = len(previous_answers) == 0
        if is_first_question and medical_history:
            hypothesis_block = self._build_pre_assessment_hypothesis(
                chief_complaint, medical_history, demographics
            )
            hypothesis_section = f"""[AI PRE-ASSESSMENT HYPOTHESIS]
Before asking any questions, AIVoN has already reviewed the patient's full medical history
and formed the following clinical reasoning frame. Every question MUST be driven by this
hypothesis — start from the most dangerous differential and work down.

{hypothesis_block}
"""
        else:
            # Subsequent questions: include history summary without re-running hypothesis LLM
            hypothesis_section = f"""[PATIENT MEDICAL HISTORY SUMMARY]
{self._format_medical_history(medical_history)}
"""

        # ── Step 2: RAG context ──────────────────────────────────────────────
        guidelines, _ = self._retrieve_context(chief_complaint)

        # ── Step 3: Build system prompt ──────────────────────────────────────
        system_prompt = f"""You are AIVoN, a clinical triage assistant supporting ER nurses.
Your task: select the single most diagnostically valuable follow-up question for the patient below.

Clinical guidelines:
{guidelines if guidelines else "Apply evidence-based emergency medicine principles."}

{hypothesis_section}

Patient demographics:
{json.dumps(demographics or {})}

Chief complaint:
{chief_complaint}

Questions already asked (do not repeat any of these):
{json.dumps(previous_answers, indent=2)}

Decision rules:
- Choose a question that has not been asked yet and was not covered in the chief complaint.
- Prioritise questions that target the most dangerous differential diagnoses first.
- If a known chronic condition exists, ask about acute complications relevant to the complaint.
- Prefer questions whose answer could change the triage classification.
- Set "done" to true when: (a) you have enough information to classify confidently, or (b) the transcript already has 5 or more questions, or (c) the presentation is clearly life-threatening.
- For visible injuries (cut, burn, rash, bleeding) with no photo in the transcript, set type to "photo_request".

Question type rules — choose carefully:
- "yes_no": any question where the answer is yes or no (e.g. "Do you have chest pain?", "Is there swelling in your leg?"). This is the most common type. Include options ["Yes", "No"].
- "scale": ONLY when explicitly asking the patient to rate intensity/severity on a number scale (e.g. "Rate your pain from 1 to 10"). Do NOT use scale for symptom presence questions. Include options ["1","2","3","4","5","6","7","8","9","10"].
- "multiple_choice": when there are 3 or more distinct options (e.g. onset timing, location). Include all options in the options array.
- "free_text": when the answer is open-ended and cannot be captured by the above types. Leave options as [].
- "photo_request": only when a visible physical finding needs to be assessed. Leave options as [].

Output valid JSON only:
- "done": boolean
- "question": object with "question" (string), "type" (one of the types above), "options" (array), "clinical_rationale" (one sentence)
- When done is true, set "question" to null
"""

        # ── Step 4: Build user message; attach images only when present ─────
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
            # Plain string avoids multimodal content-filter edge cases
            content = (
                f"Patient complaint: {chief_complaint}\n\n"
                f"Assessment so far:\n{json.dumps(previous_answers, indent=2)}"
            )

        # ── Step 5: Call GPT ─────────────────────────────────────────────────
        _fallback_questions = [
            "Are you in severe pain right now?",
            "Do you have a high fever?",
            "Is it difficult to breathe?",
            "Do you feel dizzy or faint?",
            "Have you had any loss of consciousness?",
        ]

        try:
            response_content = self._chat_complete(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": content},
                ],
                max_tokens=800,
            )
            # Strip markdown code fences GPT sometimes wraps JSON in
            cleaned = response_content.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("```")[1]
                if cleaned.startswith("json"):
                    cleaned = cleaned[4:]
                cleaned = cleaned.strip()
            result = json.loads(cleaned)
            logger.info(
                "generate_next_question: done=%s q='%s'",
                result.get("done"),
                str(result.get("question", {}).get("question", ""))[:80],
            )
            return result

        except json.JSONDecodeError as exc:
            logger.error(
                "generate_next_question: JSON parse error — raw response was: %r — error: %s",
                response_content if "response_content" in dir() else "<no response>",
                exc,
            )
        except Exception as exc:
            logger.error("generate_next_question: API error: %s", exc, exc_info=True)

        count = len(previous_answers)
        q_text = _fallback_questions[count % len(_fallback_questions)]
        return {
            "done": count >= 5,
            "question": {
                "question": q_text,
                "type": "yes_no",
                "options": ["Yes", "No"],
                "clinical_rationale": "fallback — API/parse error",
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
                "AI generated %d questions for: %s", len(questions), chief_complaint[:50]
            )
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
        context, rag_found = self._retrieve_context(chief_complaint)

        answers_text = ""
        for ans in answers:
            q = ans.get('question', '')
            a = ans.get('answer', '')
            if ans.get('image'):
                answers_text += f"Q: {q} → A: [User provided an image]\n"
            else:
                answers_text += f"Q: {q} → A: {a}\n"

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
                f"{a.get('allergen')} → {a.get('reaction')}"
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

            logger.info(
                "Triage assessment: %s (risk=%s) for '%s'",
                assessment.get("triage_level"),
                assessment.get("risk_score"),
                chief_complaint[:50],
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