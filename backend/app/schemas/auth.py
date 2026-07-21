"""Pydantic schemas for authentication."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

_EMAIL_RE = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class RegisterRequest(BaseModel):
    """Payload to create a new account."""

    email: str = Field(max_length=320)
    password: str = Field(min_length=6, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)
    role: str | None = Field(default=None, max_length=50)

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        import re

        cleaned = value.strip().lower()
        if not re.match(_EMAIL_RE, cleaned):
            raise ValueError("Adresse e-mail invalide")
        return cleaned


class LoginRequest(BaseModel):
    """Payload to sign in."""

    email: str = Field(max_length=320)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class UserResponse(BaseModel):
    """Public representation of a user account."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    full_name: str | None = None
    role: str
    is_active: bool
    created_at: datetime


class TokenResponse(BaseModel):
    """Access token returned on register/login."""

    access_token: str
    token_type: str = "bearer"
    user: UserResponse
