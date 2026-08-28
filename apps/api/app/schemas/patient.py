import uuid
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class PatientBase(BaseModel):
    name: str = Field(..., max_length=255)
    phone: str = Field(..., description="E.164 or 10-digit phone number")
    dob: Optional[date] = None
    gender: Optional[str] = Field(None, max_length=20)
    language: str = Field(default="en", max_length=10, description="Preferred language: en, hi, etc.")
    clinic_id: Optional[uuid.UUID] = None


class PatientCreate(PatientBase):
    pass


class PatientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    phone_masked: Optional[str] = None
    dob: Optional[date] = None
    gender: Optional[str] = None
    language: str
    clinic_id: Optional[uuid.UUID] = None
    is_deleted: bool
    created_at: datetime
    updated_at: datetime
