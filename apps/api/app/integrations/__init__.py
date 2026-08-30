from app.integrations.ocr import (
    GroqVisionOCRAdapter,
    MockOCRAdapter,
    OCRExtractedItem,
    OCRProvider,
    OCRResult,
    get_ocr_adapter,
)
from app.integrations.speech import (
    GroqWhisperAdapter,
    MockSpeechAdapter,
    SpeechProvider,
    TranscriptResult,
    TranscriptSegment,
    get_speech_adapter,
)
from app.integrations.storage import (
    LocalStorageAdapter,
    S3StorageAdapter,
    StorageProvider,
    get_storage_adapter,
)
from app.integrations.summary import (
    EvidencePacket,
    MockSummaryAdapter,
    SummaryProvider,
    SummaryResult,
    get_summary_adapter,
)

__all__ = [
    "SpeechProvider",
    "TranscriptResult",
    "TranscriptSegment",
    "GroqWhisperAdapter",
    "MockSpeechAdapter",
    "get_speech_adapter",
    "OCRProvider",
    "OCRResult",
    "OCRExtractedItem",
    "GroqVisionOCRAdapter",
    "MockOCRAdapter",
    "get_ocr_adapter",
    "SummaryProvider",
    "EvidencePacket",
    "SummaryResult",
    "MockSummaryAdapter",
    "get_summary_adapter",
    "StorageProvider",
    "LocalStorageAdapter",
    "S3StorageAdapter",
    "get_storage_adapter",
]
