"""
Translator Module
=================
Provides multilingual translation between patient language and the English
backend using Azure Translator (Cognitive Services).

AI-102 Concepts:
  - Azure Translator REST API (v3.0)
  - Language detection
  - Text translation with source/target language specification
  - Multi-language support (100+ languages)
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)


class Translator:
    """Handles translation between patient language and English backend.

    Uses Azure Translator REST API for text translation and language
    detection. The backend processes everything in English, and results
    are translated back to the patient's detected language.

    Attributes:
        key: Azure Translator API key.
        endpoint: Azure Translator endpoint URL.
        region: Azure Translator region (for Ocp-Apim-Subscription-Region).
    """

    def __init__(self) -> None:
        """Initialize the Translator with Azure credentials."""
        self.key: str = os.getenv("TRANSLATOR_KEY", "")
        self.endpoint: str = os.getenv(
            "TRANSLATOR_ENDPOINT",
            "https://api.cognitive.microsofttranslator.com/",
        )
        self.region: str = os.getenv("TRANSLATOR_REGION", "global")
        self._initialized = bool(self.key and self.key != "your-key")

        if not self._initialized:
            logger.warning(
                "Azure Translator credentials not configured. "
                "Translation will pass through text unchanged."
            )
        else:
            logger.info("Translator initialized (region=%s).", self.region)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def translate(
        self,
        text: str,
        target_language: str = "en",
        source_language: Optional[str] = None,
    ) -> str:
        """Translate text to the target language.

        AI-102: Azure Translator v3.0 uses the /translate endpoint.
        When source_language is omitted, the service auto-detects it.
        The Ocp-Apim-Subscription-Region header is required for
        multi-service or regional deployments.

        Args:
            text: Text to translate.
            target_language: Target language code (e.g. 'en', 'de').
            source_language: Optional source language code. If None,
                the service will auto-detect.

        Returns:
            Translated text string. Returns original text on failure.
        """
        if not self._initialized:
            return text

        if not text or not text.strip():
            return text

        # Extract base language code from locale (e.g. 'de-DE' -> 'de')
        target_lang = target_language.split("-")[0]
        source_lang = source_language.split("-")[0] if source_language else None

        # Skip if same language
        if source_lang and source_lang == target_lang:
            return text

        try:
            url = f"{self.endpoint.rstrip('/')}/translate"
            params: dict = {
                "api-version": "3.0",
                "to": target_lang,
            }
            if source_lang:
                params["from"] = source_lang

            headers = {
                "Ocp-Apim-Subscription-Key": self.key,
                "Ocp-Apim-Subscription-Region": self.region,
                "Content-type": "application/json",
                "X-ClientTraceId": str(uuid.uuid4()),
            }

            body = [{"text": text}]

            response = requests.post(
                url, params=params, headers=headers, json=body, timeout=10
            )
            response.raise_for_status()
            result = response.json()

            translated_text = result[0]["translations"][0]["text"]
            logger.info(
                "Translated '%s...' → '%s...' (%s→%s)",
                text[:30],
                translated_text[:30],
                source_lang or "auto",
                target_lang,
            )
            return translated_text

        except requests.RequestException as exc:
            logger.error("Translation HTTP error: %s", exc)
            return text
        except (KeyError, IndexError) as exc:
            logger.error("Translation parse error: %s", exc)
            return text

    def detect_language(self, text: str) -> Optional[str]:
        """Detect the language of the given text.

        AI-102: The /detect endpoint analyzes text and returns the
        detected language with a confidence score.

        Args:
            text: Text whose language to detect.

        Returns:
            Detected language code (e.g. 'de') or ``None``.
        """
        if not self._initialized or not text.strip():
            return None

        try:
            url = f"{self.endpoint.rstrip('/')}/detect"
            params = {"api-version": "3.0"}

            headers = {
                "Ocp-Apim-Subscription-Key": self.key,
                "Ocp-Apim-Subscription-Region": self.region,
                "Content-type": "application/json",
                "X-ClientTraceId": str(uuid.uuid4()),
            }

            body = [{"text": text}]
            response = requests.post(
                url, params=params, headers=headers, json=body, timeout=10
            )
            response.raise_for_status()
            result = response.json()

            detected = result[0]["language"]
            confidence = result[0].get("score", 0)
            logger.info(
                "Detected language: %s (confidence=%.2f)", detected, confidence
            )
            return detected

        except Exception as exc:
            logger.error("Language detection error: %s", exc)
            return None

    def translate_to_english(
        self, text: str, source_language: Optional[str] = None
    ) -> str:
        """Convenience method: translate patient text to English for backend.

        Args:
            text: Patient text in any language.
            source_language: Detected language code.

        Returns:
            English translation.
        """
        return self.translate(text, target_language="en", source_language=source_language)

    def translate_from_english(self, text: str, target_language: str) -> str:
        """Convenience method: translate English backend text to patient language.

        Args:
            text: English text from the backend.
            target_language: Patient's detected language code.

        Returns:
            Translated text in the patient's language.
        """
        return self.translate(text, target_language=target_language, source_language="en")