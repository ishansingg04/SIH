from typing import Any, Dict, List, Protocol
from pydantic import BaseModel, Field
from app.core.logging import logger


class OCRExtractedItem(BaseModel):
    label: str
    value: str
    confidence: float = 1.0
    page_number: int = 1


class OCRResult(BaseModel):
    raw_text: str
    items: List[OCRExtractedItem] = Field(default_factory=list)
    confidence: float = 1.0
    provider: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OCRProvider(Protocol):
    """OCR document extraction adapter protocol contract."""

    async def extract(self, object_key: str) -> OCRResult:
        """Extract text and structured medical items from document object key."""
        ...


class MockOCRAdapter:
    """Mock OCR adapter for testing and offline development."""

    async def extract(self, object_key: str) -> OCRResult:
        logger.info(f"[MOCK] Extracting text from document {object_key}")
        return OCRResult(
            raw_text="Rx: Paracetamol 500mg TDS x 3 days. Amoxicillin 500mg BD x 5 days.",
            items=[
                OCRExtractedItem(label="Medication", value="Paracetamol 500mg", confidence=0.95),
                OCRExtractedItem(label="Medication", value="Amoxicillin 500mg", confidence=0.92),
            ],
            confidence=0.94,
            provider="mock-ocr",
            metadata={"mock": True, "object_key": object_key},
        )


def get_ocr_adapter() -> OCRProvider:
    return MockOCRAdapter()
