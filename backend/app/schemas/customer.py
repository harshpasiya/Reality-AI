"""Pydantic schemas for Customer data validation and serialization."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class CustomerBase(BaseModel):
    """Shared fields across customer schemas."""

    name: str = Field(..., min_length=1, description="Full name")
    email: EmailStr = Field(..., description="Unique email address")


class CustomerCreate(CustomerBase):
    """Schema for customer registration input."""

    password: str = Field(..., min_length=8, description="Plain-text password (hashed before storage)")


class CustomerResponse(CustomerBase):
    """Schema returned by customer-related endpoints."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
