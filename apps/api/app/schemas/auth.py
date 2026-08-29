from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    phone: str = Field(..., description="E.164 or 10-digit phone number")
    name: str = Field(..., max_length=255)
    language: str = Field(default="en", max_length=10)
    consent: bool = Field(..., description="Must explicitly consent to processing terms")
    password: str = Field(..., min_length=8, description="Plaintext password to hash")
