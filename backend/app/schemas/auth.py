from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

UserRole = Literal["admin", "analyst", "procurement", "policymaker"]


class UserCreate(BaseModel):
    """Payload used to register a new user."""

    full_name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: UserRole = "analyst"

    @field_validator("full_name")
    @classmethod
    def normalize_full_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()


class LoginRequest(BaseModel):
    """Payload used to authenticate an existing user."""

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return str(value).strip().lower()


class CurrentUserResponse(BaseModel):
    """Public user representation returned by the auth APIs."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: EmailStr
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime


class TokenResponse(BaseModel):
    """JWT token payload returned by register and login endpoints."""

    access_token: str
    token_type: str = "bearer"
    user: CurrentUserResponse

