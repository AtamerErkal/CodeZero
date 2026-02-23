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

            self.openai_client = AzureOpenAI(
                azure_endpoint=endpoint,
                api_key=key,
                api_version=api_version,
            )
            self._initialized = True
            logger.info("Azure OpenAI client initialized (deployment=%s).", self.deployment)
        except Exception as exc:
            logger.error("Failed to init Azure OpenAI client: %s", exc)

    # ------------------------------------------------------------------
    # RAG: Retrieve context from knowledge base
    # ------------------------------------------------------------------

    def _retrieve_context(self, query: str) -> str:
        """Search the medical knowledge base for relevant guidelines.

        AI-102: This is the "Retrieval" step of RAG. The search query
        is derived from the patient's complaint. Results are concatenated
        and injected into the system prompt as grounding context.

        Args:
            query: Search query (usually the patient's chief complaint).

        Returns:
            Concatenated guideline text for GPT context.
        """
        if self.knowledge_indexer is None:
            return ""

        try:
            results = self.knowledge_indexer.search(query, top=3)
            if not results:
                return ""

            context_parts = []
            for r in results:
                context_parts.append(
                    f"--- Source: {r.get('source', 'Unknown')} ---\n"
                    f"{r.get('content', '')}\n"
                )
            return "\n".join(context_parts)

        except Exception as exc:
            logger.error("RAG retrieval error: %s", exc)
            return ""

    # ------------------------------------------------------------------
    # Dynamic question generation (Agentic AI)
    # ------------------------------------------------------------------

    def generate_questions(
        self,
        chief_complaint: str,
        previous_answers: Optional[list[dict]] = None,
    ) -> list[dict]:
        """Generate follow-up triage questions based on the complaint.

        AI-102 (Agentic AI): The AI dynamically decides what to ask next
        based on (a) the initial complaint, (b) retrieved medical
        guidelines, and (c) any previous answers. This multi-step
        reasoning is a hallmark of agentic AI systems.

        Args:
            chief_complaint: Patient's initial complaint in English.
            previous_answers: List of dicts with question/answer pairs.

        Returns:
            List of question dicts with keys: question, type, options.
            Types: 'yes_no', 'scale', 'multiple_choice', 'free_text'.
        """
        # Retrieve relevant medical guidelines (RAG)
        context = self._retrieve_context(chief_complaint)

        # Build previous answers context
        answers_context = ""
        if previous_answers:
            answers_context = "\nPrevious patient answers:\n"
            for ans in previous_answers:
                answers_context += f"- Q: {ans.get('question', '')} → A: {ans.get('answer', '')}\n"

        # AI-102: System prompt engineering - structure, persona, constraints
        system_prompt = f"""You are an emergency medical triage AI assistant. Your role is to
ask focused follow-up questions to assess the severity of a patient's condition.

MEDICAL GUIDELINES (use ONLY these for clinical reasoning):
{context if context else "No specific guidelines available. Use general medical knowledge."}

RULES:
1. Generate 3-5 focused follow-up questions based on the chief complaint.
2. Questions must help determine triage level: EMERGENCY, URGENT, or ROUTINE.
3. Prioritize RED FLAG assessment questions first.
4. Keep questions simple - the patient may be in distress.
5. Each question should have a clear answer type.
6. Do NOT ask for information already provided.

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
      "question": "Do you have any of these symptoms?",
      "type": "multiple_choice",
      "options": ["Sweating", "Shortness of breath", "Nausea", "Dizziness", "None"],
      "clinical_rationale": "Checking for associated cardiac symptoms"
    }}
  ]
}}
"""

        user_message = f"Chief complaint: {chief_complaint}{answers_context}\n\nGenerate triage assessment questions."

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
                temperature=0.3,
                max_tokens=1000,
            )

            result = json.loads(response.choices[0].message.content)
            questions = result.get("questions", [])
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
        context = self._retrieve_context(chief_complaint)

        answers_text = "\n".join(
            f"Q: {a.get('question', '')} → A: {a.get('answer', '')}"
            for a in answers
        )

        system_prompt = f"""You are an emergency medical triage AI. Analyze the patient's
symptoms and answers to determine the appropriate triage level.

MEDICAL GUIDELINES (use ONLY these for your assessment):
{context if context else "No specific guidelines available. Use general medical knowledge."}

ASSESSMENT RULES:
1. Base your assessment strictly on the guidelines provided.
2. Identify ALL red flags present.
3. Classify into: EMERGENCY, URGENT, or ROUTINE.
4. Provide a clear assessment summary.
5. Recommend specific actions.
6. Cite which guideline sections informed your decision.

OUTPUT FORMAT (strict JSON):
{{
  "triage_level": "EMERGENCY|URGENT|ROUTINE",
  "assessment": "Brief clinical assessment summary",
  "red_flags": ["list", "of", "identified", "red", "flags"],
  "recommended_action": "What the patient should do",
  "risk_score": 8,
  "source_guidelines": ["guideline sources used"],
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
                temperature=0.1,  # Low temperature for consistent medical assessment
                max_tokens=1000,
            )

            assessment = json.loads(response.choices[0].message.content)

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

    def create_patient_record(
        self,
        chief_complaint: str,
        assessment: dict,
        language: str = "en-US",
        eta_minutes: Optional[int] = None,
        location: Optional[dict] = None,
    ) -> dict:
        """Create a complete patient record for hospital notification.

        Args:
            chief_complaint: Patient's complaint in English.
            assessment: Triage assessment dict from assess_triage().
            language: Patient's detected language locale.
            eta_minutes: Estimated time of arrival in minutes.
            location: Patient's GPS coordinates dict.

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
        """Generate mock assessment when Azure OpenAI is unavailable."""
        complaint_lower = chief_complaint.lower()

        # Simple keyword-based triage for demo
        emergency_keywords = [
            "chest pain", "heart", "stroke", "unconscious", "bleeding",
            "can't breathe", "seizure", "severe",
        ]
        urgent_keywords = [
            "pain", "fever", "vomiting", "broken", "injury", "fall",
        ]

        # Check answers for severity
        high_severity = False
        red_flags = []
        for ans in answers:
            answer = str(ans.get("answer", "")).lower()
            if answer in ("yes", "7", "8", "9", "10"):
                high_severity = True
            if "yes" in answer and "radiat" in ans.get("question", "").lower():
                red_flags.append("pain_radiation")
            if "yes" in answer and "sweat" in answer:
                red_flags.append("diaphoresis")
            if "shortness" in answer or "breath" in answer:
                red_flags.append("dyspnea")

        if any(kw in complaint_lower for kw in emergency_keywords) or len(red_flags) >= 2:
            level = TRIAGE_EMERGENCY
            risk_score = 9
        elif any(kw in complaint_lower for kw in urgent_keywords) or high_severity:
            level = TRIAGE_URGENT
            risk_score = 6
        else:
            level = TRIAGE_ROUTINE
            risk_score = 3

        return {
            "triage_level": level,
            "assessment": f"Patient presents with {chief_complaint}. "
                         f"{'Multiple red flags identified. ' if red_flags else ''}"
                         f"Triage level: {level}.",
            "red_flags": red_flags if red_flags else ["none_identified"],
            "recommended_action": {
                TRIAGE_EMERGENCY: "Proceed to nearest ER immediately. Call emergency services if unable to travel.",
                TRIAGE_URGENT: "Visit ER or urgent care within 2 hours.",
                TRIAGE_ROUTINE: "Schedule a visit with your primary care physician. Self-care as needed.",
            }[level],
            "risk_score": risk_score,
            "source_guidelines": ["local_protocol_fallback"],
            "suspected_conditions": [chief_complaint],
            "time_sensitivity": {
                TRIAGE_EMERGENCY: "Seek ER within 10 minutes",
                TRIAGE_URGENT: "Seek medical care within 2 hours",
                TRIAGE_ROUTINE: "Schedule appointment within 48 hours",
            }[level],
        }