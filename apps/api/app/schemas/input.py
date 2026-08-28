import uuid
from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.db.models.enums import InputKind, InputStatus


class VisitInputBase(BaseModel):
    visit_id: uuid.UUID
    kind: InputKind
    object_key: Optional[str] = None
    text: Optional[str] = None
    provenance: Dict[str, Any] = Field(
        default_factory=lambda: {"source": "manual", "confidence": 1.0}
    )


class VisitInputCreate(VisitInputBase):
    pass


class VisitInputRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    visit_id: uuid.UUID
    kind: InputKind
    object_key: Optional[str] = None
    text: Optional[str] = None
    status: InputStatus
    provenance: Dict[str, Any]
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
