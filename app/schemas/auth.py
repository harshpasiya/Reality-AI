"""Pydantic schemas for authentication request/response payloads."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

# E.164: "+", country code, subscriber number — at most 15 digits in total.
PHONE_PATTERN = r"^\+[1-9]\d{7,14}$"


def normalise_email(value: str) -> str:
    """Lower-case and strip an email so ``A@x.com`` and ``a@x.com`` are one account."""
    return value.strip().lower()


class RegisterRequest(BaseModel):
    """Registration payload — works for both brokers and customers."""

    email: EmailStr
    # bcrypt only uses the first 72 bytes and newer releases raise on longer
    # input, so the limit is enforced here instead of surfacing as a 500.
    password: str = Field(..., min_length=8, max_length=72)
    name: str = Field(..., min_length=1)
    role: Literal["broker", "customer"] = Field(
        ..., description="Account type — determines which table the user is created in"
    )
    phone: str | None = Field(
        None,
        pattern=PHONE_PATTERN,
        description="Broker business phone in E.164 form, e.g. +919876543210 (brokers only)",
    )

    @field_validator("email", mode="before")
    @classmethod
    def _normalise_email(cls, value: str) -> str:
        return normalise_email(value) if isinstance(value, str) else value

    @field_validator("password")
    @classmethod
    def _password_bytes(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 bytes when UTF-8 encoded")
        return value

    @model_validator(mode="after")
    def _phone_for_brokers_only(self) -> "RegisterRequest":
        if self.phone is not None and self.role != "broker":
            raise ValueError("phone can only be set for broker accounts")
        return self


class AuthUser(BaseModel):
    """User profile data returned within TokenResponse."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    name: str
    role: Literal["broker", "customer"]


class TokenResponse(BaseModel):
    """JWT token and authenticated user returned on successful register or login."""

    access_token: str
    token_type: str = "bearer"
    user: AuthUser


class UserResponse(AuthUser):
    """Authenticated user profile returned by GET /auth/me."""

    created_at: datetime
    phone: str | None = Field(None, description="Broker's own phone (brokers only)")
