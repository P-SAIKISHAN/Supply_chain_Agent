from datetime import datetime
import re
from typing import Literal

from pydantic import BaseModel, Field, validator

UserRole = Literal["admin", "analyst", "procurement", "policymaker"]
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class UserCreate(BaseModel):
    """Payload used to register a new user."""

    full_name: str = Field(min_length=2, max_length=150)
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=8, max_length=128)
    role: UserRole = "analyst"

    @validator("full_name")
    def normalize_full_name(cls, value: str) -> str:
        return value.strip()

    @validator("email")
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not EMAIL_PATTERN.match(normalized):
            raise ValueError("Invalid email address")
        return normalized


class LoginRequest(BaseModel):
    """Payload used to authenticate an existing user."""

    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=1, max_length=128)

    @validator("email")
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not EMAIL_PATTERN.match(normalized):
            raise ValueError("Invalid email address")
        return normalized


class CurrentUserResponse(BaseModel):
    """Public user representation returned by the auth APIs."""

    id: int
    full_name: str
    email: str
    role: UserRole
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class TokenResponse(BaseModel):
    """JWT token payload returned by register and login endpoints."""

    access_token: str
    token_type: str = "bearer"
    user: CurrentUserResponse
