import uuid
from typing import Optional, TYPE_CHECKING
from sqlalchemy import Boolean, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin, UUIDMixin
from app.db.models.enums import UserRole

if TYPE_CHECKING:
    from app.db.models.clinic import Clinic


class User(Base, UUIDMixin, TimestampMixin):
    """Clinic staff or system operator user account."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role_enum", native_enum=False),
        nullable=False,
        default=UserRole.PATIENT,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    clinic_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("clinics.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Relationships
    clinic: Mapped[Optional["Clinic"]] = relationship("Clinic", back_populates="users")
