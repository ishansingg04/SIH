import uuid
from datetime import date, datetime
from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.db.models.clinic import Clinic
    from app.db.models.visit import Visit
    from app.db.models.user import User


class Patient(Base, UUIDMixin, TimestampMixin):
    """Patient demographics and identity profile."""

    __tablename__ = "patients"

    phone_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    phone_masked: Mapped[str] = mapped_column(String(20), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    dob: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    gender: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    clinic_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("clinics.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=True,
        index=True,
    )

    # Consent fields
    consent_version: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    consent_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    consent_language: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    consent_actor: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Relationships
    clinic: Mapped[Optional["Clinic"]] = relationship("Clinic", back_populates="patients")
    visits: Mapped[List["Visit"]] = relationship("Visit", back_populates="patient", cascade="all, delete-orphan")
    user: Mapped[Optional["User"]] = relationship("User")
