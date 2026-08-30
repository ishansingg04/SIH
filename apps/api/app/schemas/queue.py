import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.db.models.enums import IntakePathway, VisitStatus
from app.schemas.visit import VisitRead


class Disposition(str, Enum):
    FOLLOW_UP = "FOLLOW_UP"
    REFERRED = "REFERRED"
    DISCHARGED = "DISCHARGED"
    PRESCRIBED = "PRESCRIBED"
    NO_ACTION = "NO_ACTION"


class QueueEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    visit_id: uuid.UUID
    clinic_id: uuid.UUID
    position: int
    state: VisitStatus
    called_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    # Contextual fields computed from linked visit/patient
    patient_name: Optional[str] = None
    token: Optional[str] = None
    intake_pathway: Optional[IntakePathway] = None
    has_summary: bool = False
    wait_minutes: int = 0


class QueueSummary(BaseModel):
    clinic_id: uuid.UUID
    waiting_count: int = 0
    in_progress_count: int = 0
    completed_today_count: int = 0
    oldest_wait_minutes: int = 0


class QueueListResponse(BaseModel):
    entries: List[QueueEntryRead]
    summary: QueueSummary
    as_of: datetime = Field(default_factory=datetime.utcnow)


class ClaimResponse(BaseModel):
    queue_entry: QueueEntryRead
    visit: VisitRead


class VisitCompleteRequest(BaseModel):
    disposition: Disposition = Field(..., description="Clinical disposition category")
    note: Optional[str] = Field(default=None, description="Doctor consultation notes / instructions")


class VisitCompleteResponse(BaseModel):
    visit_id: uuid.UUID
    token: str
    status: VisitStatus
    disposition: Disposition
    note: Optional[str] = None
    completed_at: datetime


class VisitActionRequest(BaseModel):
    reason: Optional[str] = Field(default=None, description="Optional explanation for cancellation or no-show")

