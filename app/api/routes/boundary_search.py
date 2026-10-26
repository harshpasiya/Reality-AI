"""Boundary search route — POST /listings/search-boundary (polygon search)."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.boundary import BoundarySearchRequest
from app.schemas.listing import ListingResponse
from app.services import geo_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Listings"])

BOUNDARY_RESULT_LIMIT = 50


class _NeverRaised(Exception):
    """Placeholder for an AI exception class that isn't defined."""


def boundary_listing_ids(db: Session, polygon: list[list[float]]) -> list[int]:
    """IDs of listings inside *polygon*, by the AI's rule when it is installed.

    Uses ``ai.rag.boundary_filter.get_candidates()`` so the map's boundary
    search and ``/chat`` with a polygon can never disagree; falls back to the
    equivalent PostGIS query (``ST_MakeValid`` + ``ST_Contains``) during
    isolated backend development.  Shared by this route and ``/chat``.

    Raises ``HTTPException`` 422 for a polygon the AI rejects and 503 when the
    boundary filter's database query fails.
    """
    try:
        from ai.rag import boundary_filter  # type: ignore[import-untyped]
    except Exception as exc:  # ImportError, or a module that fails while importing
        log = logger.warning if isinstance(exc, ImportError) else logger.exception
        log("ai.rag.boundary_filter not available — using backend polygon query")
        return geo_service.boundary_candidate_ids(db, polygon)

    filter_error = getattr(boundary_filter, "BoundaryFilterError", _NeverRaised)
    try:
        return list(boundary_filter.get_candidates(polygon))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except filter_error:
        logger.exception("Boundary filter failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Boundary search is temporarily unavailable",
        )


@router.post(
    "/listings/search-boundary",
    response_model=list[ListingResponse],
    summary="Polygon (hand-drawn) boundary search for listings",
)
def search_boundary(
    body: BoundarySearchRequest,
    db: Session = Depends(get_db),
) -> list[ListingResponse]:
    """Return available / under-offer listings inside the hand-drawn polygon.

    Coordinates are ``[lat, lng]`` pairs (3-1000 points; the ring is closed
    automatically).  Self-crossing shapes are repaired, not rejected — the
    same rule ``/chat`` applies through the AI module.
    """
    ids = boundary_listing_ids(db, body.polygon)
    return geo_service.visible_listings_by_ids(  # type: ignore[return-value]
        db, sorted(ids), limit=BOUNDARY_RESULT_LIMIT
    )
