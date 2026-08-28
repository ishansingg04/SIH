import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict
from app.db.models.enums import VisitStatus


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


class QueueSummary(BaseModel):
    clinic_id: uuid.UUID
    waiting_count: int
    in_progress_count: int
    completed_today_count: int
    oldest_wait_minutes: Optional[int] = 0
