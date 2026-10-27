"""Tests for listing endpoints — POST /listings, GET /listings/{id}, GET /listings/search."""

import pytest
from fastapi.testclient import TestClient

from tests.conftest import register_broker, auth_header


# Coordinates for test listings — real Surat points
ADAJAN = {"lat": 21.1702, "lng": 72.8311}
VESU = {"lat": 21.1550, "lng": 72.7716}  # ~6 km from Adajan


def _listing_payload(**overrides) -> dict:
    """Build a minimal valid ListingCreate payload."""
    base = {
        "title": "Test Flat in Adajan",
        "description": "A cozy 2BHK flat",
        "price": 4500000,
        "property_type": "flat",
        "lat": ADAJAN["lat"],
        "lng": ADAJAN["lng"],
        "carpet_area": 900,
        "built_up_area": 1100,
        "rooms": {"bedrooms": 2, "bathrooms": 1},
    }
    base.update(overrides)
    return base


class TestCreateListing:
    """POST /listings."""

    def test_create_listing_as_broker(self, client: TestClient):
        token = register_broker(client)["access_token"]
        resp = client.post(
            "/listings",
            json=_listing_payload(),
            headers=auth_header(token),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Test Flat in Adajan"
        assert data["property_type"] == "flat"
        assert "id" in data
        assert "amenities" in data  # field must exist per AGENTS.md, even if null

    def test_create_listing_without_auth_401(self, client: TestClient):
        resp = client.post("/listings", json=_listing_payload())
        assert resp.status_code == 401

    def test_create_listing_invalid_property_type_422(self, client: TestClient):
        token = register_broker(client)["access_token"]
        resp = client.post(
            "/listings",
            json=_listing_payload(property_type="villa"),
            headers=auth_header(token),
        )
        assert resp.status_code == 422


class TestGetListing:
    """GET /listings/{listing_id}."""

    def test_get_existing_listing(self, client: TestClient):
        token = register_broker(client)["access_token"]
        create_resp = client.post(
            "/listings",
            json=_listing_payload(),
            headers=auth_header(token),
        )
        listing_id = create_resp.json()["id"]

        resp = client.get(f"/listings/{listing_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == listing_id

    def test_get_nonexistent_listing_404(self, client: TestClient):
        resp = client.get("/listings/999999")
        assert resp.status_code == 404


class TestSearchListings:
    """GET /listings/search (radius search)."""

    def test_radius_search_includes_nearby(self, client: TestClient):
        """Seed a listing at Adajan and search from Adajan — should appear."""
        token = register_broker(client)["access_token"]
        client.post(
            "/listings",
            json=_listing_payload(),
            headers=auth_header(token),
        )

        resp = client.get("/listings/search", params={
            "lat": ADAJAN["lat"],
            "lng": ADAJAN["lng"],
            "radius_km": 2,
        })
        assert resp.status_code == 200
        results = resp.json()
        assert len(results) >= 1

    def test_radius_search_excludes_distant(self, client: TestClient):
        """Seed a listing at Adajan, search from Vesu with 1km radius — the Adajan listing should NOT appear."""
        token = register_broker(client)["access_token"]
        create_resp = client.post(
            "/listings",
            json=_listing_payload(),  # at Adajan
            headers=auth_header(token),
        )
        adajan_listing_id = create_resp.json()["id"]

        resp = client.get("/listings/search", params={
            "lat": VESU["lat"],
            "lng": VESU["lng"],
            "radius_km": 1,  # Vesu is ~6km from Adajan
        })
        assert resp.status_code == 200
        results = resp.json()
        result_ids = [r["id"] for r in results]
        assert adajan_listing_id not in result_ids, (
            f"Adajan listing {adajan_listing_id} should NOT appear in a 1km Vesu search"
        )
