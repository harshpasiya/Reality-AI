"""Pydantic schemas for Broker data validation and serialization."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.listing import ListingResponse


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


class BrokerPublicProfile(BaseModel):
    """What any visitor may see about a broker (``GET /brokers/{id}/public``).

    Email and phone are deliberately absent: a customer gets the phone number
    only by sending an enquiry (``POST /listings/{id}/leads``).
    """

    id: int
    name: str
    member_since: datetime
    active_listings: int = Field(..., description="Available and under-offer listings")
    listings: list[ListingResponse] = Field(
        default_factory=list, description="Newest visible listings, at most 50"
    )
