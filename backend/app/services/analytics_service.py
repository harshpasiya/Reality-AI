"""Broker analytics service — aggregated views and leads per listing."""

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.broker import Broker
from app.models.lead import Lead
from app.models.listing import Listing
from app.schemas.analytics import BrokerAnalyticsResponse, ListingAnalyticsItem


def get_broker_analytics(
    db: Session, broker_id: int
) -> BrokerAnalyticsResponse | None:
    """Return aggregated listing, view and lead analytics for a broker.

    Covers every listing the broker owns, including sold and withdrawn
    ones.  Returns ``None`` if no broker with ``broker_id`` exists.
    """
    broker = db.query(Broker).filter(Broker.id == broker_id).first()
    if not broker:
        return None

    # Only the columns needed — never load geometry or embeddings here
    listings = (
        db.query(Listing.id, Listing.title, Listing.status, Listing.view_count)
        .filter(Listing.broker_id == broker_id)
        .order_by(Listing.id)
        .all()
    )
    if not listings:
        return BrokerAnalyticsResponse(
            total_listings=0,
            total_views=0,
            total_leads=0,
            listings_breakdown=[],
        )

    # Grouped query counting leads per listing
    lead_counts_query = (
        db.query(Lead.listing_id, func.count(Lead.id).label("cnt"))
        .filter(Lead.listing_id.in_([l.id for l in listings]))
        .group_by(Lead.listing_id)
        .all()
    )
    counts_map = {listing_id: cnt for listing_id, cnt in lead_counts_query}

    breakdown = [
        ListingAnalyticsItem(
            listing_id=l.id,
            title=l.title,
            status=l.status,
            view_count=l.view_count,
            lead_count=counts_map.get(l.id, 0),
        )
        for l in listings
    ]

    return BrokerAnalyticsResponse(
        total_listings=len(breakdown),
        total_views=sum(item.view_count for item in breakdown),
        total_leads=sum(item.lead_count for item in breakdown),
        listings_breakdown=breakdown,
    )
