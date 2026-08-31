import uuid
from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import ForeignKey, Integer, JSON, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.db.models.visit import Visit


class PatientInterview(Base, UUIDMixin, TimestampMixin):
    """Conversational intake state machine recording patient turns and structured facts."""

    __tablename__ = "patient_interviews"

    visit_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("visits.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(30), default="IN_PROGRESS", nullable=False, index=True)
    language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
    pathway: Mapped[str] = mapped_column(String(20), default="ALLOPATHIC", nullable=False)

    # Conversation state stored as JSON
    turns: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    extracted_facts: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    missing_slots: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    answered_questions: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    red_flags: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    current_question_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    question_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_questions: Mapped[int] = mapped_column(Integer, default=6, nullable=False)

    # Relationship back to Visit
    visit: Mapped["Visit"] = relationship("Visit", back_populates="interview")
