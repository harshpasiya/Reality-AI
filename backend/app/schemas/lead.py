"""Pydantic schemas for leads — a customer's explicit enquiry on a listing."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

LeadStatus = Literal["new", "contacted", "visit_scheduled", "closed", "lost"]


class LeadCreate(BaseModel):
    """Body for ``POST /listings/{id}/leads`` ("Contact broker")."""

    message: str | None = Field(
        None, max_length=2000, description="What the customer wants to ask the broker"
    )
    conversation_id: int | None = Field(
        None, description="Chat that led to this enquiry (must belong to the customer)"
    )


class LeadStatusUpdate(BaseModel):
    """Body for ``PATCH /leads/{id}``."""

    status: LeadStatus


class LeadResponse(BaseModel):
    """A lead as stored."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    listing_id: int
    customer_id: int
    message: str | None = None
    status: LeadStatus
    conversation_id: int | None = None
    created_at: datetime
    updated_at: datetime


class BrokerContact(BaseModel):
    """Broker contact details, revealed only after a customer creates a lead."""

    name: str
    phone: str | None = None


class LeadCreateResponse(LeadResponse):
    """Response to ``POST /listings/{id}/leads``."""

    broker: BrokerContact


class BrokerLeadItem(LeadResponse):
    """A lead in the broker's inbox, with who asked and about which listing."""

    listing_title: str
    customer_name: str
    customer_email: str
