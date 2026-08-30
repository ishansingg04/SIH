import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.db.models.enums import SummaryReviewStatus


class SummaryReviewDecision(str, Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    EDIT = "EDIT"


class FactItem(BaseModel):
    value: Any
    source: str = Field(default="patient_reported", description="transcript | document | ayush_form | model_inference")
    source_id: Optional[str] = Field(default=None, description="Input ID or Document reference")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    review_state: str = Field(default="unreviewed", description="unreviewed | confirmed | edited | rejected")


class ModelSuggestionItem(BaseModel):
    suggestion: str
    confidence: float = Field(default=0.85, ge=0.0, le=1.0)
    category: str = Field(default="assistive_consideration", description="assistive_consideration | red_flag | recommendation")


class UncertaintyLabelItem(BaseModel):
    field: str
    reason: str
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class AYUSHAssessmentSchema(BaseModel):
    prakriti: Dict[str, Any] = Field(default_factory=dict, description="AYUSH - Prakriti: constitution baseline")
    vikriti: Dict[str, Any] = Field(default_factory=dict, description="AYUSH - Vikriti: current imbalance/symptom pattern")
    agni: Dict[str, Any] = Field(default_factory=dict, description="AYUSH - Agni: appetite & digestive fire")
    koshtha: Dict[str, Any] = Field(default_factory=dict, description="AYUSH - Koshtha: bowel regularity & context")
    sattva: Dict[str, Any] = Field(default_factory=dict, description="AYUSH - Sattva: mental stamina, sleep & wellbeing")


class SummaryPayloadSchema(BaseModel):
    chief_complaint: Optional[Dict[str, Any]] = Field(default=None, description="Primary reason for visit with provenance")
    patient_reported: Dict[str, Any] = Field(default_factory=dict, description="Facts reported directly by patient")
    document_extracted: Dict[str, Any] = Field(default_factory=dict, description="Facts extracted from uploaded documents")
    ayush_assessment: Dict[str, Any] = Field(default_factory=dict, description="Structured Dashavidha Pariksha AYUSH facts")
    model_suggestions: List[Dict[str, Any]] = Field(default_factory=list, description="AI-generated assistive differential suggestions")
    uncertainty_labels: List[Dict[str, Any]] = Field(default_factory=list, description="Areas of ambiguity or low confidence")
    red_flags_for_doctor_review: List[Dict[str, Any]] = Field(default_factory=list, description="Clinical flags requiring doctor attention")
    unknowns: List[str] = Field(default_factory=list, description="Explicitly missing or uncollected information")


class SummaryCreate(BaseModel):
    visit_id: uuid.UUID
    version: int = 1
    payload_json: SummaryPayloadSchema
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class SummaryGenerateRequest(BaseModel):
    force_refresh: bool = Field(default=False, description="Force re-generation of summary bypassing existing draft")


class SummaryReviewRequest(BaseModel):
    decision: SummaryReviewDecision = Field(description="APPROVE | REJECT | EDIT")
    edits: Optional[Dict[str, Any]] = Field(default=None, description="Doctor-corrected payload fields")
    doctor_notes: Optional[str] = Field(default=None, description="Clinical notes or rationale for review")


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


class SummaryDetailResponse(BaseModel):
    status: str = Field(default="READY", description="READY | PROCESSING | FAILED")
    version: int
    summary_id: uuid.UUID
    visit_id: uuid.UUID
    review_status: SummaryReviewStatus
    confidence: float
    payload: Dict[str, Any]
    facts: List[Dict[str, Any]] = Field(default_factory=list)
    flags: List[Dict[str, Any]] = Field(default_factory=list)
    reviewed_by: Optional[uuid.UUID] = None
    doctor_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class PatientHistoryResponse(BaseModel):
    patient_id: uuid.UUID
    patient_name: str
    total_visits: int
    visits: List[Dict[str, Any]] = Field(default_factory=list)
    medications: List[Dict[str, Any]] = Field(default_factory=list)
    conditions: List[Dict[str, Any]] = Field(default_factory=list)
    ayush_history: List[Dict[str, Any]] = Field(default_factory=list)
    continuity_labels: List[Dict[str, Any]] = Field(default_factory=list)
