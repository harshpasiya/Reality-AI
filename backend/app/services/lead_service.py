"""Lead service — explicit customer enquiries and the broker's follow-up."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.conversation import Conversation
from app.models.customer import Customer
from app.models.lead import Lead
from app.models.listing import Listing, VISIBLE_STATUSES
from app.schemas.lead import LeadCreate


class LeadError(Exception):
    """Base class for lead business-rule failures."""


class DuplicateLeadError(LeadError):
    """The customer already has a lead on this listing."""


class ListingUnavailableError(LeadError):
    """The listing is sold or withdrawn."""


class ConversationNotFoundError(LeadError):
    """``conversation_id`` does not exist or belongs to another customer."""


def create_lead(
    db: Session, listing: Listing, customer: Customer, data: LeadCreate
) -> Lead:
    """Create the one lead a customer may have on a listing."""
    if listing.status not in VISIBLE_STATUSES:
        raise ListingUnavailableError(f"Listing {listing.id} is {listing.status}")

    if data.conversation_id is not None:
        owned = (
            db.query(Conversation.id)
            .filter(
                Conversation.id == data.conversation_id,
                Conversation.customer_id == customer.id,
            )
            .first()
        )
        if owned is None:
            raise ConversationNotFoundError(f"Conversation {data.conversation_id} not found")

    existing = (
        db.query(Lead.id)
        .filter(Lead.listing_id == listing.id, Lead.customer_id == customer.id)
        .first()
    )
    if existing is not None:
        raise DuplicateLeadError("You have already contacted the broker about this listing")

    lead = Lead(
        listing_id=listing.id,
        customer_id=customer.id,
        message=data.message,
        conversation_id=data.conversation_id,
    )
    db.add(lead)
    try:
        db.commit()
    except IntegrityError as exc:  # concurrent duplicate hit the unique constraint
        db.rollback()
        raise DuplicateLeadError(
            "You have already contacted the broker about this listing"
        ) from exc
    db.refresh(lead)
    return lead


def broker_leads(
    db: Session,
    broker_id: int,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[tuple[Lead, Listing, Customer]]:
    """Leads on a broker's listings, newest first."""
    query = (
        db.query(Lead, Listing, Customer)
        .join(Listing, Lead.listing_id == Listing.id)
        .join(Customer, Lead.customer_id == Customer.id)
        .filter(Listing.broker_id == broker_id)
    )
    if status is not None:
        query = query.filter(Lead.status == status)
    return query.order_by(Lead.created_at.desc(), Lead.id.desc()).offset(offset).limit(limit).all()


def get_lead(db: Session, lead_id: int) -> Lead | None:
    """Fetch a lead by id, or ``None``."""
    return db.query(Lead).filter(Lead.id == lead_id).first()


def set_status(db: Session, lead: Lead, status: str) -> Lead:
    """Move a lead along the broker's follow-up pipeline."""
    lead.status = status
    db.commit()
    db.refresh(lead)
    return lead
