import uuid
from typing import Optional, TYPE_CHECKING
from sqlalchemy import Boolean, Enum, ForeignKey, Index, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin, UUIDMixin
from app.db.models.enums import InputKind, InputStatus

if TYPE_CHECKING:
    from app.db.models.visit import Visit


class VisitInput(Base, UUIDMixin, TimestampMixin):
    """Raw evidence captured during patient intake (audio, documents, forms)."""

    __tablename__ = "visit_inputs"

    visit_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("visits.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[InputKind] = mapped_column(
        Enum(InputKind, name="input_kind_enum", native_enum=False),
        nullable=False,
        index=True,
    )
    object_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[InputStatus] = mapped_column(
        Enum(InputStatus, name="input_status_enum", native_enum=False),
        default=InputStatus.PENDING,
        nullable=False,
    )
    provenance: Mapped[dict] = mapped_column(
        JSON,
        default=lambda: {"source": "manual", "confidence": 1.0},
        nullable=False,
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    visit: Mapped["Visit"] = relationship("Visit", back_populates="inputs")

    __table_args__ = (
        Index("ix_visit_inputs_visit_kind", "visit_id", "kind"),
    )
