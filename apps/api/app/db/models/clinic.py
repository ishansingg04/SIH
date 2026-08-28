from typing import List, TYPE_CHECKING
from sqlalchemy import Boolean, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.db.models.user import User
    from app.db.models.patient import Patient
    from app.db.models.visit import Visit


class Clinic(Base, UUIDMixin, TimestampMixin):
    """Healthcare facility or Primary Health Center."""

    __tablename__ = "clinics"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    address: Mapped[str] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    ayush_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    supported_languages: Mapped[list] = mapped_column(JSON, default=lambda: ["en", "hi"], nullable=False)
    queue_policy: Mapped[dict] = mapped_column(JSON, default=lambda: {"mode": "FIFO", "prefix": "A"}, nullable=False)

    # Relationships
    users: Mapped[List["User"]] = relationship("User", back_populates="clinic", cascade="all, delete-orphan")
    patients: Mapped[List["Patient"]] = relationship("Patient", back_populates="clinic")
    visits: Mapped[List["Visit"]] = relationship("Visit", back_populates="clinic")
