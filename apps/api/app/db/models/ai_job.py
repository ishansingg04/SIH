import uuid
from typing import Optional, TYPE_CHECKING
from sqlalchemy import Enum, ForeignKey, Index, Integer, JSON, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin, UUIDMixin
from app.db.models.enums import AIJobStatus, AIJobType

if TYPE_CHECKING:
    from app.db.models.visit import Visit


class AIJob(Base, UUIDMixin, TimestampMixin):
    """Asynchronous background processing job for transcription, OCR, or summary."""

    __tablename__ = "ai_jobs"

    visit_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("visits.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[AIJobType] = mapped_column(
        Enum(AIJobType, name="ai_job_type_enum", native_enum=False),
        nullable=False,
        index=True,
    )
    status: Mapped[AIJobStatus] = mapped_column(
        Enum(AIJobStatus, name="ai_job_status_enum", native_enum=False),
        default=AIJobStatus.PENDING,
        nullable=False,
        index=True,
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    provider: Mapped[str] = mapped_column(String(50), default="mock", nullable=False)
    error_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(100), unique=True, nullable=True, index=True)
    payload_in: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    payload_out: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Relationships
    visit: Mapped["Visit"] = relationship("Visit", back_populates="ai_jobs")

    __table_args__ = (
        Index("ix_ai_jobs_status_created", "status", "created_at"),
    )
