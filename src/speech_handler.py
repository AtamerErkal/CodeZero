"""
Speech Handler Module
=====================
Handles voice input via Azure Speech Services with automatic language
detection. Supports 6+ languages for the patient-facing triage app.

AI-102 Concepts:
  - Azure Cognitive Services Speech SDK
  - Speech-to-Text (STT) with real-time recognition
  - AutoDetectSourceLanguageConfig for multi-language support
  - SpeechRecognizer with audio configuration
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# Supported languages for auto-detection
# AI-102: Azure Speech AutoDetectSourceLanguageConfig supports up to 10 languages
# in Continuous recognition mode, but only UP TO 4 in DetectAudioAtStart mode
# (which is used with recognize_once()).
#
# We define two lists:
#   AUTO_DETECT_LANGUAGES  — max 4, used with recognize_once() / DetectAudioAtStart
#   SUPPORTED_LANGUAGES    — full list, used for display / translator fallback
#
# The 4 most common languages for emergency triage are chosen for detection:
AUTO_DETECT_LANGUAGES = [
    "en-US",  # English  — global default
    "de-DE",  # German   — project primary region (Stuttgart)
    "tr-TR",  # Turkish  — project secondary region
    "ar-SA",  # Arabic   — RTL test + Middle East coverage
]

# Full list kept for UI display names and translator coverage
SUPPORTED_LANGUAGES = [
    "en-US",  # English (US)
    "de-DE",  # German
    "tr-TR",  # Turkish
    "ar-SA",  # Arabic (Saudi Arabia)
    "fr-FR",  # French
    "es-ES",  # Spanish
    "it-IT",  # Italian
    "pt-BR",  # Portuguese (Brazil)
    "ru-RU",  # Russian
    "zh-CN",  # Chinese (Mandarin)
]

# Language display names for UI
LANGUAGE_NAMES: dict[str, str] = {
    "en-US": "English",
    "de-DE": "Deutsch",
    "tr-TR": "Türkçe",
    "ar-SA": "العربية",
    "fr-FR": "Français",
    "es-ES": "Español",
    "it-IT": "Italiano",
    "pt-BR": "Português",
    "ru-RU": "Русский",
    "zh-CN": "中文",
}


class SpeechHandler:
    """Handles speech-to-text with automatic language detection.

    Provides methods for both real-time microphone input and processing
    of audio files/streams. Auto-detects the patient's language from
    a configurable candidate list.

    Attributes:
        speech_key: Azure Speech API key.
        speech_region: Azure Speech service region.
        speech_config: Configured SpeechConfig instance.
    """

    def __init__(self) -> None:
        """Initialize the Speech Handler with Azure credentials."""
        self.speech_key: str = os.getenv("SPEECH_KEY", "")
        self.speech_region: str = os.getenv("SPEECH_REGION", "westeurope")
        self.speech_config = None
        self._initialized = False
        self._init_config()

    def _init_config(self) -> None:
        """Initialize Azure Speech SDK configuration.

        AI-102: SpeechConfig holds the subscription key and region.
        It is reused across multiple recognition sessions.
        """
        if not self.speech_key or self.speech_key == "your-key":
            logger.warning(
                "Azure Speech credentials not configured. "
                "Voice input will be unavailable; text input still works."
            )
            return
        try:
            import azure.cognitiveservices.speech as speechsdk

            self.speech_config = speechsdk.SpeechConfig(
                subscription=self.speech_key,
                region=self.speech_region,
            )
            # AI-102: Enable detailed output for richer result metadata
            self.speech_config.output_format = (
                speechsdk.OutputFormat.Detailed
            )
            self._initialized = True
            logger.info("Azure Speech config initialized (region=%s).", self.speech_region)
        except ImportError:
            logger.error(
                "azure-cognitiveservices-speech package not installed."
            )
        except Exception as exc:
            logger.error("Failed to init Speech config: %s", exc)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def recognize_from_microphone(self) -> Optional[dict]:
        """Perform single-shot recognition from the default microphone.

        AI-102: AutoDetectSourceLanguageConfig allows the Speech service
        to detect which language the user is speaking from a candidate
        list. This is critical for multilingual triage applications.

        Returns:
            Dict with ``text`` (transcribed), ``language`` (detected locale),
            and ``confidence`` if successful, or ``None`` on failure.
        """
        if not self._initialized:
            logger.warning("Speech not initialized.")
            return None

        try:
            import azure.cognitiveservices.speech as speechsdk

            # AI-102: Configure auto-detection from candidate languages
            # FIX: DetectAudioAtStart (recognize_once) supports max 4 languages
            auto_detect_config = (
                speechsdk.languageconfig.AutoDetectSourceLanguageConfig(
                    languages=AUTO_DETECT_LANGUAGES
                )
            )

            # AI-102: AudioConfig.use_default_microphone() routes audio
            # from the system's default microphone device
            audio_config = speechsdk.audio.AudioConfig(
                use_default_microphone=True
            )

            recognizer = speechsdk.SpeechRecognizer(
                speech_config=self.speech_config,
                auto_detect_source_language_config=auto_detect_config,
                audio_config=audio_config,
            )

            logger.info("Listening for speech input...")
            result = recognizer.recognize_once()

            return self._process_result(result)

        except Exception as exc:
            logger.error("Speech recognition error: %s", exc)
            return None

    def convert_browser_audio_to_wav(self, raw_bytes: bytes, source_suffix: str = ".webm") -> Optional[str]:
        """Convert browser audio bytes (WebM/Opus) to a WAV temp file.

        ``st.audio_input`` returns raw WebM/Opus bytes from the browser.
        Azure Speech SDK's ``AudioConfig(filename=...)`` only accepts real
        WAV files with proper RIFF headers. This method uses ffmpeg (if
        available) or pydub to convert the browser audio before recognition.

        Args:
            raw_bytes: Raw audio bytes from ``st.audio_input``.
            source_suffix: File extension hint for the input format
                           (e.g. '.webm', '.ogg', '.mp4').

        Returns:
            Path to a temporary WAV file, or ``None`` if conversion failed.
        """
        import subprocess
        import tempfile

        # Write raw browser audio to a temp file
        try:
            with tempfile.NamedTemporaryFile(suffix=source_suffix, delete=False) as src_file:
                src_file.write(raw_bytes)
                src_path = src_file.name

            wav_path = src_path.replace(source_suffix, ".wav")

            # Strategy 1: ffmpeg (most reliable, handles all browser formats)
            try:
                subprocess.run(
                    [
                        "ffmpeg", "-y", "-i", src_path,
                        "-ar", "16000",          # 16 kHz — Azure Speech requirement
                        "-ac", "1",              # mono
                        "-sample_fmt", "s16",    # 16-bit PCM
                        wav_path,
                    ],
                    check=True,
                    capture_output=True,
                    timeout=30,
                )
                os.unlink(src_path)
                logger.info("ffmpeg converted browser audio to WAV: %s", wav_path)
                return wav_path
            except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as ffmpeg_err:
                logger.warning("ffmpeg not available or failed (%s), trying pydub.", ffmpeg_err)

            # Strategy 2: pydub (requires ffmpeg internally but may be on PATH differently)
            try:
                from pydub import AudioSegment
                audio = AudioSegment.from_file(src_path)
                audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)
                audio.export(wav_path, format="wav")
                os.unlink(src_path)
                logger.info("pydub converted browser audio to WAV: %s", wav_path)
                return wav_path
            except Exception as pydub_err:
                logger.warning("pydub conversion failed: %s", pydub_err)

            os.unlink(src_path)
            return None

        except Exception as exc:
            logger.error("Audio conversion error: %s", exc)
            return None

    def recognize_from_audio_file(self, audio_path: str) -> Optional[dict]:
        """Recognize speech from an audio file (WAV format).

        Args:
            audio_path: Path to a WAV audio file.

        Returns:
            Recognition result dict or ``None``.
        """
        if not self._initialized:
            logger.warning("Speech not initialized.")
            return None

        try:
            import azure.cognitiveservices.speech as speechsdk

            # FIX: DetectAudioAtStart (used with recognize_once) supports max 4 languages
            auto_detect_config = (
                speechsdk.languageconfig.AutoDetectSourceLanguageConfig(
                    languages=AUTO_DETECT_LANGUAGES
                )
            )

            audio_config = speechsdk.audio.AudioConfig(filename=audio_path)

            recognizer = speechsdk.SpeechRecognizer(
                speech_config=self.speech_config,
                auto_detect_source_language_config=auto_detect_config,
                audio_config=audio_config,
            )

            result = recognizer.recognize_once()
            return self._process_result(result)

        except Exception as exc:
            logger.error("Speech recognition from file error: %s", exc)
            return None

    def text_to_speech(self, text: str, language: str = "en-US") -> bool:
        """Convert text to speech output.

        AI-102: Text-to-Speech can be used to read triage results aloud,
        improving accessibility for visually impaired patients.

        Args:
            text: Text to synthesize.
            language: BCP-47 language code for voice selection.

        Returns:
            True if synthesis succeeded.
        """
        if not self._initialized:
            logger.warning("Speech not initialized.")
            return False

        try:
            import azure.cognitiveservices.speech as speechsdk

            self.speech_config.speech_synthesis_language = language
            synthesizer = speechsdk.SpeechSynthesizer(
                speech_config=self.speech_config
            )
            result = synthesizer.speak_text_async(text).get()

            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                logger.info("TTS completed for language %s.", language)
                return True
            else:
                logger.warning("TTS failed: %s", result.reason)
                return False

        except Exception as exc:
            logger.error("TTS error: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _process_result(self, result) -> Optional[dict]:
        """Process a speech recognition result.

        Args:
            result: SpeechRecognitionResult from the SDK.

        Returns:
            Parsed result dict or ``None``.
        """
        import azure.cognitiveservices.speech as speechsdk

        if result.reason == speechsdk.ResultReason.RecognizedSpeech:
            # AI-102: The auto-detect language result is stored in a
            # property bag, accessed via PropertyId
            detected_language = result.properties.get(
                speechsdk.PropertyId.SpeechServiceConnection_AutoDetectSourceLanguageResult,
                "en-US",
            )
            logger.info(
                "Recognized: '%s' (language=%s)",
                result.text,
                detected_language,
            )
            return {
                "text": result.text,
                "language": detected_language,
                "confidence": getattr(result, "confidence", None),
            }

        elif result.reason == speechsdk.ResultReason.NoMatch:
            logger.warning("No speech recognized.")
            return None

        elif result.reason == speechsdk.ResultReason.Canceled:
            cancellation = result.cancellation_details

            # FIX: error_code attribute changed across SDK versions (int vs enum vs absent)
            # Use getattr with safe int conversion to avoid AttributeError
            raw_code = getattr(cancellation, "error_code", None)
            raw_details = getattr(cancellation, "error_details", "") or ""
            try:
                error_code_int = int(raw_code) if raw_code is not None else -1
            except (TypeError, ValueError):
                error_code_int = -1

            logger.error(
                "Speech recognition canceled — reason=%s code=%s details=%s",
                cancellation.reason,
                error_code_int,
                raw_details,
            )

            # Provide actionable error messages for common failure codes
            if error_code_int == 4 or "authentication" in raw_details.lower():
                logger.error(
                    "Azure Speech authentication failed. "
                    "Check SPEECH_KEY and SPEECH_REGION in your .env file."
                )
            elif error_code_int == 7 or "connection" in raw_details.lower():
                logger.error(
                    "Azure Speech connection failed. "
                    "Check SPEECH_REGION in your .env file (e.g. westeurope)."
                )
            return None

        return None

    @staticmethod
    def get_language_name(locale: str) -> str:
        """Get the display name for a language locale.

        Args:
            locale: BCP-47 locale string (e.g. 'de-DE').

        Returns:
            Human-readable language name.
        """
        return LANGUAGE_NAMES.get(locale, locale)

    @staticmethod
    def is_available() -> bool:
        """Check if Azure Speech SDK is installed.

        Returns:
            True if the speech SDK is importable.
        """
        try:
            import azure.cognitiveservices.speech  # noqa: F401
            return True
        except ImportError:
            return False