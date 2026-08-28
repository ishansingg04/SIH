import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from app.db.models.enums import UserRole


class UserBase(BaseModel):
    email: EmailStr
    full_name: str = Field(..., max_length=255)
    role: UserRole = Field(default=UserRole.PATIENT)
    is_active: bool = Field(default=True)
    clinic_id: Optional[uuid.UUID] = None


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, description="Plaintext password to hash")


class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_seconds: int
    user: UserRead


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
