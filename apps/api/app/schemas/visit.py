import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.db.models.enums import IntakePathway, VisitStatus
from app.schemas.ayush import (
    AgniSchema,
    KoshthaSchema,
    PrakritiSchema,
    SattvaSchema,
    VikritiSchema,
)


class VisitBase(BaseModel):
    patient_id: uuid.UUID
    clinic_id: uuid.UUID
    intake_pathway: IntakePathway = Field(default=IntakePathway.ALLOPATHIC)
    consent_given: bool = Field(default=True, description="Explicit patient consent indicator")
    consent_language: str = Field(default="en", max_length=10)

    # Optional initial AYUSH intake payload
    prakriti: Optional[PrakritiSchema] = None
    vikriti: Optional[VikritiSchema] = None
    agni: Optional[AgniSchema] = None
    koshtha: Optional[KoshthaSchema] = None
    sattva: Optional[SattvaSchema] = None
    ayush_notes: Optional[str] = None


class VisitCreate(VisitBase):
    pass


class VisitStatusUpdate(BaseModel):
    status: VisitStatus


class VisitRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    patient_id: uuid.UUID
    clinic_id: uuid.UUID
    status: VisitStatus
    intake_pathway: IntakePathway
    token: str
    service_date: date
    consent_at: Optional[datetime] = None
    consent_language: str
    created_by: Optional[uuid.UUID] = None

    # AYUSH Dashavidha Pariksha fields
    prakriti: Optional[Dict[str, Any]] = None
    vikriti: Optional[Dict[str, Any]] = None
    agni: Optional[Dict[str, Any]] = None
    koshtha: Optional[Dict[str, Any]] = None
    sattva: Optional[Dict[str, Any]] = None
    ayush_notes: Optional[str] = None

    created_at: datetime
    updated_at: datetime
