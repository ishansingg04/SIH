"""Speech transcription provider adapters.

Supports:
- GroqWhisperAdapter: Hosted Groq Whisper API (primary path)
- MockSpeechAdapter: Deterministic mock for offline development/testing
"""

from typing import Any, Dict, List, Optional, Protocol

import httpx
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.exceptions import DependencyUnavailableException
from app.core.logging import logger


class TranscriptSegment(BaseModel):
    start_time: float
    end_time: float
    text: str
    confidence: float = 1.0


class TranscriptResult(BaseModel):
    text: str
    language: str
    segments: List[TranscriptSegment] = Field(default_factory=list)
    provider: str
    is_fallback: bool = False
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SpeechProvider(Protocol):
    """Speech transcription adapter protocol contract."""

    async def transcribe(
        self,
        audio_bytes: bytes,
        language: str = "en",
        filename: str = "audio.webm",
    ) -> TranscriptResult:
        """Transcribe audio bytes and return structured transcript."""
        ...


class GroqWhisperAdapter:
    """Hosted Groq Whisper API adapter — primary transcription path."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.GROQ_API_KEY
        self.endpoint = "https://api.groq.com/openai/v1/audio/transcriptions"

    async def transcribe(
        self,
        audio_bytes: bytes,
        language: str = "en",
        filename: str = "audio.webm",
    ) -> TranscriptResult:
        if not self.api_key:
            raise DependencyUnavailableException(
                "GROQ_API_KEY is not configured for Groq Whisper transcription"
            )

        # Map language codes to Whisper language names
        language_map = {"en": "en", "hi": "hi", "english": "en", "hindi": "hi"}
        whisper_lang = language_map.get(language.lower(), language)

        # Determine MIME type from filename extension
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "webm"
        mime_map = {
            "webm": "audio/webm",
            "wav": "audio/wav",
            "mp3": "audio/mpeg",
            "ogg": "audio/ogg",
            "mp4": "audio/mp4",
            "m4a": "audio/mp4",
        }
        mime_type = mime_map.get(ext, "audio/webm")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                logger.info(
                    f"Initiating Groq Whisper transcription "
                    f"(lang={whisper_lang}, size={len(audio_bytes)} bytes, file={filename})"
                )

                response = await client.post(
                    self.endpoint,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    files={"file": (filename, audio_bytes, mime_type)},
                    data={
                        "model": "whisper-large-v3",
                        "language": whisper_lang,
                        "response_format": "verbose_json",
                    },
                )
                response.raise_for_status()
                result_data = response.json()

            # Parse segments if available
            segments = []
            for seg in result_data.get("segments", []):
                segments.append(
                    TranscriptSegment(
                        start_time=float(seg.get("start", 0)),
                        end_time=float(seg.get("end", 0)),
                        text=seg.get("text", "").strip(),
                        confidence=1.0 - float(seg.get("avg_logprob", -0.5)) * -1
                        if seg.get("avg_logprob")
                        else 0.9,
                    )
                )

            return TranscriptResult(
                text=result_data.get("text", "").strip(),
                language=result_data.get("language", whisper_lang),
                segments=segments,
                provider="groq-whisper",
                is_fallback=False,
                metadata={
                    "model": "whisper-large-v3",
                    "duration": result_data.get("duration"),
                    "filename": filename,
                },
            )

        except httpx.HTTPStatusError as exc:
            logger.error(f"Groq Whisper HTTP error: {exc.response.status_code}")
            raise DependencyUnavailableException(
                f"Groq Whisper provider returned HTTP {exc.response.status_code}"
            )
        except httpx.TimeoutException:
            logger.error("Groq Whisper request timed out")
            raise DependencyUnavailableException("Groq Whisper provider timed out")
        except Exception as exc:
            logger.error(f"Groq Whisper transcription failed: {exc}")
            raise DependencyUnavailableException(f"Groq Whisper provider error: {exc}")


class MockSpeechAdapter:
    """Deterministic Mock Speech adapter for offline development and testing."""

    async def transcribe(
        self,
        audio_bytes: bytes,
        language: str = "en",
        filename: str = "audio.webm",
    ) -> TranscriptResult:
        logger.info(
            f"[MOCK] Transcribing {filename} with language={language} "
            f"({len(audio_bytes)} bytes)"
        )
        sample_text = (
            "मरीज को दो दिन से बुखार और खांसी है।"
            if language == "hi"
            else "Patient reports two days of mild fever and dry cough."
        )
        return TranscriptResult(
            text=sample_text,
            language=language,
            segments=[
                TranscriptSegment(
                    start_time=0.0,
                    end_time=3.2,
                    text=sample_text,
                    confidence=0.98,
                )
            ],
            provider="mock-speech",
            is_fallback=False,
            metadata={"mock": True, "filename": filename},
        )


def get_speech_adapter() -> SpeechProvider:
    """Factory selecting speech provider based on application configuration."""
    if settings.WHISPER_PROVIDER_MODE == "groq-hosted":
        return GroqWhisperAdapter()
    return MockSpeechAdapter()
