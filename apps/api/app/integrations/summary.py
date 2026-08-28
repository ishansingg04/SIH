from typing import Any, Dict, List, Optional, Protocol
from pydantic import BaseModel, Field
from app.core.logging import logger


class EvidencePacket(BaseModel):
    visit_id: str
    transcripts: List[str] = Field(default_factory=list)
    document_texts: List[str] = Field(default_factory=list)
    ayush_intake: Optional[Dict[str, Any]] = None
    patient_history: Optional[Dict[str, Any]] = None


class SummaryResult(BaseModel):
    patient_reported: Dict[str, Any] = Field(default_factory=dict)
    document_extracted: Dict[str, Any] = Field(default_factory=dict)
    ayush_assessment: Dict[str, Any] = Field(default_factory=dict)
    model_suggestions: List[Dict[str, Any]] = Field(default_factory=list)
    uncertainty_labels: List[Dict[str, Any]] = Field(default_factory=list)
    confidence: float = 1.0
    provider: str


class SummaryProvider(Protocol):
    """Clinical AI Summarization adapter protocol contract."""

    async def summarize(self, evidence: EvidencePacket) -> SummaryResult:
        """Generate structured clinical summary from combined evidence."""
        ...


class MockSummaryAdapter:
    """Mock Summary adapter producing strict, schema-compliant summary structures."""

    async def summarize(self, evidence: EvidencePacket) -> SummaryResult:
        logger.info(f"[MOCK] Generating clinical summary for visit {evidence.visit_id}")

        ayush_data = evidence.ayush_intake or {}

        return SummaryResult(
            patient_reported={
                "chief_complaint": "Fever and cough for 2 days",
                "symptoms": ["Mild fever", "Dry cough"],
                "duration_days": 2,
            },
            document_extracted={
                "prior_prescriptions": ["Paracetamol 500mg"],
                "last_recorded_date": "2026-08-20",
            },
            ayush_assessment={
                "prakriti": ayush_data.get("prakriti", {"primary_dosha": "VATA_PITTA"}),
                "vikriti": ayush_data.get("vikriti", {"aggravated_doshas": ["VATA"], "symptom_pattern": "Dryness, restlessness"}),
                "agni": ayush_data.get("agni", {"agni_type": "VISHAMA", "appetite_level": "Irregular"}),
                "koshtha": ayush_data.get("koshtha", {"koshtha_type": "KRURA", "bowel_regularity": "Constipated"}),
                "sattva": ayush_data.get("sattva", {"sattva_type": "MADHYAMA", "sleep_quality": "Disturbed"}),
            },
            model_suggestions=[
                {
                    "suggestion": "Evaluate for upper respiratory tract infection; consider Vata-pacifying dietary advice if AYUSH pathway active.",
                    "confidence": 0.88,
                    "category": "assistive_consideration",
                }
            ],
            uncertainty_labels=[
                {
                    "field": "prior_prescriptions",
                    "reason": "OCR handwriting confidence at 85%",
                }
            ],
            confidence=0.92,
            provider="mock-summary-engine",
        )


def get_summary_adapter() -> SummaryProvider:
    return MockSummaryAdapter()
