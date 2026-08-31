import uuid
from datetime import date, datetime, timezone
from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin, UUIDMixin
from app.db.models.enums import IntakePathway, VisitStatus

if TYPE_CHECKING:
    from app.db.models.clinic import Clinic
    from app.db.models.patient import Patient
    from app.db.models.queue import QueueEntry
    from app.db.models.input import VisitInput
    from app.db.models.ai_job import AIJob
    from app.db.models.summary import Summary
    from app.db.models.interview import PatientInterview



class Visit(Base, UUIDMixin, TimestampMixin):
    """Clinical encounter representing a single patient visit."""

    __tablename__ = "visits"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("clinics.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[VisitStatus] = mapped_column(
        Enum(VisitStatus, name="visit_status_enum", native_enum=False),
        default=VisitStatus.WAITING,
        nullable=False,
        index=True,
    )
    intake_pathway: Mapped[IntakePathway] = mapped_column(
        Enum(IntakePathway, name="intake_pathway_enum", native_enum=False),
        default=IntakePathway.ALLOPATHIC,
        nullable=False,
        index=True,
    )
    token: Mapped[str] = mapped_column(String(20), nullable=False)
    service_date: Mapped[date] = mapped_column(Date, default=lambda: datetime.now(timezone.utc).date(), nullable=False)
    consent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    consent_language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)

    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # AYUSH Dashavidha Pariksha Structured Fields
    # Stored as validated JSON structures with clinician-reviewable format
    prakriti: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    vikriti: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    agni: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    koshtha: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    sattva: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    ayush_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    clinic: Mapped["Clinic"] = relationship("Clinic", back_populates="visits")
    patient: Mapped["Patient"] = relationship("Patient", back_populates="visits")
    queue_entry: Mapped[Optional["QueueEntry"]] = relationship("QueueEntry", back_populates="visit", uselist=False, cascade="all, delete-orphan")
    inputs: Mapped[List["VisitInput"]] = relationship("VisitInput", back_populates="visit", cascade="all, delete-orphan")
    ai_jobs: Mapped[List["AIJob"]] = relationship("AIJob", back_populates="visit", cascade="all, delete-orphan")
    summaries: Mapped[List["Summary"]] = relationship("Summary", back_populates="visit", cascade="all, delete-orphan")
    interview: Mapped[Optional["PatientInterview"]] = relationship("PatientInterview", back_populates="visit", uselist=False, cascade="all, delete-orphan")



    __table_args__ = (
        UniqueConstraint("clinic_id", "token", "service_date", name="uq_visits_clinic_token_date"),
        Index("ix_visits_clinic_status_date", "clinic_id", "status", "service_date"),
    )
