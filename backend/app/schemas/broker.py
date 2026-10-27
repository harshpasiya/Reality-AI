"""Pydantic schemas for Broker data validation and serialization."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class BrokerBase(BaseModel):
    """Shared fields across broker schemas."""

    name: str = Field(..., min_length=1, description="Full name")
    email: EmailStr = Field(..., description="Unique email address")


class BrokerCreate(BrokerBase):
    """Schema for broker registration input."""

    password: str = Field(..., min_length=8, description="Plain-text password (hashed before storage)")
    phone: str | None = Field(None, description="Phone number (hashed before storage)")


class BrokerResponse(BrokerBase):
    """Schema returned by broker-related endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
