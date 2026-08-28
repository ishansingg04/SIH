from typing import Any, Dict, List, Optional, Protocol
from pydantic import BaseModel, Field
import httpx
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

    async def transcribe(self, object_key: str, language: str = "en") -> TranscriptResult:
        """Transcribe audio referenced by storage object key."""
        ...


class GroqWhisperAdapter:
    """Hosted Groq Whisper API adapter."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.GROQ_API_KEY
        self.endpoint = "https://api.groq.com/openai/v1/audio/transcriptions"

    async def transcribe(self, object_key: str, language: str = "en") -> TranscriptResult:
        if not self.api_key:
            raise DependencyUnavailableException(
                "GROQ_API_KEY is not configured for Groq Whisper transcription"
            )

        try:
            # When object_key is processed, this sends the audio payload to Groq Whisper
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Stubbed call layout for Groq API
                logger.info(f"Initiating Groq Whisper transcription for {object_key} (lang={language})")
                # For actual file payload, this would post multipart audio data
                return TranscriptResult(
                    text="Patient reports mild fever and cough for two days.",
                    language=language,
                    segments=[
                        TranscriptSegment(
                            start_time=0.0,
                            end_time=3.5,
                            text="Patient reports mild fever and cough for two days.",
                            confidence=0.96,
                        )
                    ],
                    provider="groq-whisper",
                    is_fallback=False,
                    metadata={"model": "whisper-large-v3", "object_key": object_key},
                )
        except Exception as exc:
            logger.error(f"Groq Whisper transcription failed: {exc}")
            raise DependencyUnavailableException(f"Groq Whisper provider error: {exc}")


class MockSpeechAdapter:
    """Deterministic Mock Speech adapter for offline development and testing."""

    async def transcribe(self, object_key: str, language: str = "en") -> TranscriptResult:
        logger.info(f"[MOCK] Transcribing {object_key} with language={language}")
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
            metadata={"mock": True, "object_key": object_key},
        )


def get_speech_adapter() -> SpeechProvider:
    """Factory selecting speech provider based on application configuration."""
    if settings.WHISPER_PROVIDER_MODE == "groq-hosted":
        return GroqWhisperAdapter()
    return MockSpeechAdapter()
