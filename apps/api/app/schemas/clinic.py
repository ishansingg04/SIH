import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ClinicBase(BaseModel):
    name: str = Field(..., max_length=255, description="Clinic or facility name")
    code: str = Field(..., max_length=50, description="Unique clinic identifier code")
    address: Optional[str] = Field(None, max_length=500)
    is_active: bool = Field(default=True)
    ayush_enabled: bool = Field(default=True, description="Enables AYUSH Dashavidha Pariksha pathway")
    supported_languages: List[str] = Field(default_factory=lambda: ["en", "hi"])
    queue_policy: Dict[str, Any] = Field(default_factory=lambda: {"mode": "FIFO", "prefix": "A"})


class ClinicCreate(ClinicBase):
    pass


class ClinicRead(ClinicBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
