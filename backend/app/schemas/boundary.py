"""Pydantic schemas for polygon boundary search requests."""

import math

from pydantic import BaseModel, Field, field_validator

# Same limits as ai.rag.boundary_filter.get_candidates() (AGENTS.md §5), so the
# map's boundary search and a chat message with a polygon accept the same shapes.
MIN_POLYGON_POINTS = 3
MAX_POLYGON_POINTS = 1000


def validate_polygon(points: list[list[float]]) -> list[list[float]]:
    """Validate ``[[lat, lng], ...]`` points and return a closed ring.

    Rejects fewer than 3 or more than 1000 points, non-finite values and
    out-of-range coordinates.  Self-crossing shapes are *not* rejected: the
    query repairs them with ``ST_MakeValid``, matching the AI module.
    """
    if len(points) < MIN_POLYGON_POINTS:
        raise ValueError("Polygon must contain at least 3 points")
    if len(points) > MAX_POLYGON_POINTS:
        raise ValueError(
            f"Polygon vertex count exceeds maximum limit of {MAX_POLYGON_POINTS} points"
        )

    for idx, pt in enumerate(points):
        if not isinstance(pt, (list, tuple)) or len(pt) != 2:
            raise ValueError(
                f"Point at index {idx} must be a 2-element list [lat, lng]"
            )
        lat, lng = pt
        if not (math.isfinite(lat) and math.isfinite(lng)):
            raise ValueError(f"Point at index {idx} has a non-finite coordinate")
        if not (-90 <= lat <= 90):
            raise ValueError(
                f"Point at index {idx} has invalid latitude {lat} (must be in [-90, 90])"
            )
        if not (-180 <= lng <= 180):
            raise ValueError(
                f"Point at index {idx} has invalid longitude {lng} (must be in [-180, 180])"
            )

    # Auto-close the polygon ring if the first and last points differ
    first_pt = points[0]
    last_pt = points[-1]
    if first_pt[0] != last_pt[0] or first_pt[1] != last_pt[1]:
        points = list(points) + [list(first_pt)]

    return points


class BoundarySearchRequest(BaseModel):
    """Payload for POST /listings/search-boundary.

    Polygon is a list of ``[lat, lng]`` coordinate pairs.
    """

    polygon: list[list[float]] = Field(
        ...,
        description="List of [lat, lng] coordinates forming a drawn polygon (3-1000 points)",
    )

    @field_validator("polygon")
    @classmethod
    def validate_and_close_polygon(
        cls, points: list[list[float]]
    ) -> list[list[float]]:
        """Ensure valid coordinates, 3-1000 vertices, and auto-close the ring."""
        return validate_polygon(points)
