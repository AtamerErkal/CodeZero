"""
Safety Filter Module
====================
Optional content safety layer using Azure AI Content Safety. Filters
harmful or inappropriate content from patient input and AI output.

AI-102 Concepts:
  - Azure AI Content Safety API
  - Text content analysis for harmful content categories
  - Severity thresholds for medical context
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class SafetyFilter:
    """Content safety filter using Azure AI Content Safety.

    Analyzes text input for harmful content categories (hate, violence,
    self-harm, sexual) and blocks or flags content exceeding thresholds.

    In a medical context, some violence/self-harm content is expected
    (patients describing injuries), so thresholds are adjusted higher.

    Attributes:
        endpoint: Azure Content Safety endpoint.
        key: Azure Content Safety API key.
    """

    # Medical context allows higher threshold for violence/self-harm
    # because patients legitimately describe injuries and symptoms.
    DEFAULT_THRESHOLDS = {
        "Hate": 2,       # Block moderate+ hate speech
        "Violence": 4,   # Allow violence descriptions (injuries)
        "SelfHarm": 4,   # Allow self-harm descriptions (symptoms)
        "Sexual": 2,     # Block moderate+ sexual content
    }

    def __init__(self) -> None:
        """Initialize the Safety Filter with Azure credentials."""
        self.endpoint: str = os.getenv("CONTENT_SAFETY_ENDPOINT", "")
        self.key: str = os.getenv("CONTENT_SAFETY_KEY", "")
        self.client = None
        self._initialized = False
        self._init_client()

    def _init_client(self) -> None:
        """Initialize Azure Content Safety client.

        AI-102: ContentSafetyClient analyzes text and images for
        harmful content across four categories, each with severity
        levels from 0 (safe) to 6 (severe).
        """
        if not self.endpoint or not self.key or self.key == "your-key":
            logger.info(
                "Content Safety not configured. Safety filtering disabled."
            )
            return

        try:
            from azure.ai.contentsafety import ContentSafetyClient
            from azure.core.credentials import AzureKeyCredential

            self.client = ContentSafetyClient(
                endpoint=self.endpoint,
                credential=AzureKeyCredential(self.key),
            )
            self._initialized = True
            logger.info("Content Safety client initialized.")
        except Exception as exc:
            logger.error("Failed to init Content Safety client: %s", exc)

    def analyze_text(
        self,
        text: str,
        thresholds: Optional[dict[str, int]] = None,
    ) -> dict:
        """Analyze text for harmful content.

        AI-102: The analyze_text method returns severity scores (0-6)
        for each category. Content is flagged if any category exceeds
        the configured threshold.

        Args:
            text: Text to analyze.
            thresholds: Optional custom thresholds per category.

        Returns:
            Dict with is_safe (bool), categories (severity scores),
            and flagged_categories (list of exceeded categories).
        """
        if not self._initialized:
            return {"is_safe": True, "categories": {}, "flagged_categories": []}

        active_thresholds = thresholds or self.DEFAULT_THRESHOLDS

        try:
            from azure.ai.contentsafety.models import AnalyzeTextOptions

            request = AnalyzeTextOptions(text=text)
            response = self.client.analyze_text(request)

            categories = {}
            flagged = []

            for item in response.categories_analysis:
                category_name = item.category.value if hasattr(item.category, "value") else str(item.category)
                severity = item.severity
                categories[category_name] = severity

                threshold = active_thresholds.get(category_name, 4)
                if severity >= threshold:
                    flagged.append(category_name)

            is_safe = len(flagged) == 0

            if not is_safe:
                logger.warning(
                    "Content flagged: %s (categories: %s)",
                    flagged,
                    categories,
                )

            return {
                "is_safe": is_safe,
                "categories": categories,
                "flagged_categories": flagged,
            }

        except Exception as exc:
            logger.error("Content safety analysis error: %s", exc)
            # Fail open — allow content if safety service fails
            return {"is_safe": True, "categories": {}, "flagged_categories": []}