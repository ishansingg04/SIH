import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.db.models.enums import SummaryReviewStatus


class SummaryPayloadSchema(BaseModel):
    patient_reported: Dict[str, Any] = Field(default_factory=dict, description="Facts reported directly by patient")
    document_extracted: Dict[str, Any] = Field(default_factory=dict, description="Facts extracted from uploaded documents")
    ayush_assessment: Dict[str, Any] = Field(default_factory=dict, description="Structured Dashavidha Pariksha AYUSH facts")
    model_suggestions: List[Dict[str, Any]] = Field(default_factory=list, description="AI-generated assistive differential suggestions")
    uncertainty_labels: List[Dict[str, Any]] = Field(default_factory=list, description="Areas of ambiguity or low confidence")


class SummaryCreate(BaseModel):
    visit_id: uuid.UUID
    version: int = 1
    payload_json: SummaryPayloadSchema
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class SummaryReviewUpdate(BaseModel):
    review_status: SummaryReviewStatus
    doctor_notes: Optional[str] = None


class SummaryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    visit_id: uuid.UUID
    version: int
    payload_json: Dict[str, Any]
    confidence: float
    reviewed_by: Optional[uuid.UUID] = None
    review_status: SummaryReviewStatus
    doctor_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
