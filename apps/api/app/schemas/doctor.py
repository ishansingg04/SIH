import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.db.models.enums import InputKind, InputStatus, SummaryReviewStatus
from app.schemas.queue import QueueEntryRead
from app.schemas.summary import SummaryRead
from app.schemas.visit import VisitRead


class InputSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kind: InputKind
    status: InputStatus
    text_snippet: Optional[str] = None
    object_key: Optional[str] = None
    confidence: Optional[float] = None
    created_at: datetime


class DoctorWorkspaceResponse(BaseModel):
    visit: VisitRead
    queue_entry: Optional[QueueEntryRead] = None
    patient_name: str
    patient_gender: Optional[str] = None
    patient_age: Optional[int] = None
    patient_language: str = "en"
    summaries: List[SummaryRead] = Field(default_factory=list)
    inputs: List[InputSummary] = Field(default_factory=list)


class SummaryReviewRequest(BaseModel):
    review_status: SummaryReviewStatus = Field(..., description="Target review status (CONFIRMED, REJECTED, EDITED)")
    doctor_notes: Optional[str] = Field(default=None, description="Doctor observations or amendments")


class SummaryReviewResponse(BaseModel):
    summary: SummaryRead
    visit_id: uuid.UUID
    reviewed_by: uuid.UUID
    reviewed_at: datetime
