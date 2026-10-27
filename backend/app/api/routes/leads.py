"""Lead routes — POST and GET /listings/{id}/leads[/mine] (customer), PATCH /leads/{id} (broker)."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.broker import Broker
from app.models.customer import Customer
from app.models.lead import Lead
from app.schemas.lead import (
    BrokerContact,
    LeadCreate,
    LeadCreateResponse,
    LeadResponse,
    LeadStatusUpdate,
)
from app.services import lead_service, listing_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Leads"])


@router.post(
    "/listings/{listing_id}/leads",
    response_model=LeadCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Contact the broker about a listing (customer only, once per listing)",
)
def create_lead(
    listing_id: int,
    body: LeadCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> LeadCreateResponse:
    """Record the enquiry and return the broker's contact details.

    This is the only way a lead is created — chat search results count as
    views, not leads.  The broker's phone is revealed here and nowhere public.
    """
    if not isinstance(current_user, Customer):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only customers can contact brokers",
        )
    listing = listing_service.get_listing(db, listing_id)
    if listing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Listing with id {listing_id} not found",
        )

    try:
        lead = lead_service.create_lead(db, listing, current_user, body)
    except lead_service.ConversationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except (lead_service.DuplicateLeadError, lead_service.ListingUnavailableError) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    broker = listing.broker
    return LeadCreateResponse(
        **LeadResponse.model_validate(lead).model_dump(),
        broker=BrokerContact(name=broker.name, phone=broker.phone),
    )


@router.get(
    "/listings/{listing_id}/leads/mine",
    response_model=LeadCreateResponse,
    summary="The customer's own enquiry on a listing, with the broker's contact",
)
def get_my_lead(
    listing_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> LeadCreateResponse:
    """Lets a customer who already enquired see the broker's phone again (404 if not)."""
    if not isinstance(current_user, Customer):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only customers have enquiries",
        )
    listing = listing_service.get_listing(db, listing_id)
    lead = (
        db.query(Lead)
        .filter(Lead.listing_id == listing_id, Lead.customer_id == current_user.id)
        .first()
        if listing is not None
        else None
    )
    if lead is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="You have not contacted the broker about this listing",
        )
    broker = listing.broker
    return LeadCreateResponse(
        **LeadResponse.model_validate(lead).model_dump(),
        broker=BrokerContact(name=broker.name, phone=broker.phone),
    )


@router.patch(
    "/leads/{lead_id}",
    response_model=LeadResponse,
    summary="Update a lead's follow-up status (broker who owns the listing)",
)
def update_lead_status(
    lead_id: int,
    body: LeadStatusUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> LeadResponse:
    """Move the lead to new / contacted / visit_scheduled / closed / lost."""
    if not isinstance(current_user, Broker):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only brokers can update leads",
        )
    lead = lead_service.get_lead(db, lead_id)
    if lead is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Lead {lead_id} not found"
        )
    if lead.listing.broker_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only update leads on your own listings",
        )
    return lead_service.set_status(db, lead, body.status)  # type: ignore[return-value]
