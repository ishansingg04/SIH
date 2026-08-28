import uuid
from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.db.models.enums import AIJobStatus, AIJobType


class AIJobCreate(BaseModel):
    visit_id: uuid.UUID
    type: AIJobType
    provider: str = Field(default="mock")
    payload_in: Optional[Dict[str, Any]] = None
    idempotency_key: Optional[str] = None


class AIJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    visit_id: uuid.UUID
    type: AIJobType
    status: AIJobStatus
    attempts: int
    provider: str
    error_code: Optional[str] = None
    idempotency_key: Optional[str] = None
    payload_in: Optional[Dict[str, Any]] = None
    payload_out: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
