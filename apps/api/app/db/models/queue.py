import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin, UUIDMixin
from app.db.models.enums import VisitStatus

if TYPE_CHECKING:
    from app.db.models.visit import Visit


class QueueEntry(Base, UUIDMixin, TimestampMixin):
    """Real-time clinic waiting queue entry linked to a visit."""

    __tablename__ = "queue_entries"

    visit_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("visits.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    clinic_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("clinics.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    state: Mapped[VisitStatus] = mapped_column(
        Enum(VisitStatus, name="queue_state_enum", native_enum=False),
        default=VisitStatus.WAITING,
        nullable=False,
        index=True,
    )
    called_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    visit: Mapped["Visit"] = relationship("Visit", back_populates="queue_entry")

    __table_args__ = (
        Index("ix_queue_clinic_state", "clinic_id", "state"),
    )
