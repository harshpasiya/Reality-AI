"""Broker dashboard routes — GET /brokers/{id}/listings and GET /brokers/{id}/leads."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.broker import Broker
from app.schemas.lead import BrokerLeadItem, LeadResponse, LeadStatus
from app.schemas.listing import BrokerListingItem, ListingResponse, ListingStatus
from app.services import lead_service, listing_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Brokers"])


def _require_self(broker_id: int, current_user) -> None:
    """Basic ownership check (not full RBAC): the broker may only see their own data."""
    if not isinstance(current_user, Broker) or current_user.id != broker_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access your own broker account",
        )


@router.get(
    "/brokers/{broker_id}/listings",
    response_model=list[BrokerListingItem],
    summary="The broker's own listings, every status, with view and lead counts",
)
def get_broker_listings(
    broker_id: int,
    status_filter: Optional[ListingStatus] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> list[BrokerListingItem]:
    """Newest first; optional ``?status=`` filter."""
    _require_self(broker_id, current_user)
    rows = listing_service.broker_listings(
        db, broker_id, status=status_filter, limit=limit, offset=offset
    )
    return [
        BrokerListingItem(
            **ListingResponse.model_validate(listing).model_dump(),
            view_count=listing.view_count,
            lead_count=lead_count,
        )
        for listing, lead_count in rows
    ]


@router.get(
    "/brokers/{broker_id}/leads",
    response_model=list[BrokerLeadItem],
    summary="Leads on the broker's listings (inbox)",
)
def get_broker_leads(
    broker_id: int,
    status_filter: Optional[LeadStatus] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> list[BrokerLeadItem]:
    """Newest first; optional ``?status=`` filter."""
    _require_self(broker_id, current_user)
    rows = lead_service.broker_leads(
        db, broker_id, status=status_filter, limit=limit, offset=offset
    )
    return [
        BrokerLeadItem(
            **LeadResponse.model_validate(lead).model_dump(),
            listing_title=listing.title,
            customer_name=customer.name,
            customer_email=customer.email,
        )
        for lead, listing, customer in rows
    ]
