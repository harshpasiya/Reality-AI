"""Localities route — GET /localities (the Surat areas the AI search knows)."""

from fastapi import APIRouter
from pydantic import BaseModel

from app.db.surat_reference_data import LOCALITIES

router = APIRouter(tags=["Localities"])


class Locality(BaseModel):
    """A searchable area: its centre point and the AI search radius."""

    name: str
    lat: float
    lng: float
    radius_m: int


@router.get(
    "/localities",
    response_model=list[Locality],
    summary="Surat localities the AI search recognises, A-Z",
)
def list_localities() -> list[Locality]:
    """Used by the frontend to place a new listing without typing coordinates.

    The data is the backend's copy of the AI gazetteer; ``tests/test_seed.py``
    checks it still matches ``ai.nlu.gazetteer``.
    """
    return [
        Locality(name=name, lat=loc["lat"], lng=loc["lng"], radius_m=loc["radius_m"])
        for name, loc in sorted(LOCALITIES.items())
    ]
