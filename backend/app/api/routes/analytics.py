"""Broker analytics routes — GET /brokers/{id}/analytics."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.broker import Broker
from app.schemas.analytics import BrokerAnalyticsResponse
from app.services import analytics_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Analytics"])


@router.get(
    "/brokers/{broker_id}/analytics",
    response_model=BrokerAnalyticsResponse,
    summary="Fetch broker analytics (views and leads per listing)",
)
def get_analytics(
    broker_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> BrokerAnalyticsResponse:
    """Return total listings, total leads, and per-listing breakdown.

    Ownership check: the authenticated user must be a broker matching
    ``broker_id``.  (Note: this is a basic ownership check, not full RBAC).
    """
    if not isinstance(current_user, Broker) or current_user.id != broker_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only access analytics for your own broker account",
        )

    analytics = analytics_service.get_broker_analytics(db, broker_id)
    if analytics is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Broker {broker_id} not found",
        )

    return analytics
