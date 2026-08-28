import uuid
from datetime import date
from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import Boolean, Date, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.db.models.clinic import Clinic
    from app.db.models.visit import Visit


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

    # Relationships
    clinic: Mapped[Optional["Clinic"]] = relationship("Clinic", back_populates="patients")
    visits: Mapped[List["Visit"]] = relationship("Visit", back_populates="patient", cascade="all, delete-orphan")
