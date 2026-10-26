"""Tests for polygon boundary search endpoint — POST /listings/search-boundary."""

import pytest
from fastapi.testclient import TestClient

from tests.conftest import register_broker, auth_header, listing_payload


# Coordinates forming a polygon around Adajan neighbourhood
ADAJAN_POLYGON = [
    [21.1800, 72.8200],
    [21.1800, 72.8400],
    [21.1600, 72.8400],
    [21.1600, 72.8200],
]


class TestBoundarySearch:
    """POST /listings/search-boundary."""

    def test_boundary_search_valid_polygon(self, client: TestClient):
        # Seed a listing inside Adajan
        token = register_broker(client)["access_token"]
        client.post(
            "/listings",
            json=listing_payload(title="Flat in Adajan Polygon", price=5000000),
            headers=auth_header(token),
        )

        resp = client.post(
            "/listings/search-boundary",
            json={"polygon": ADAJAN_POLYGON},
        )
        assert resp.status_code == 200
        listings = resp.json()
        assert len(listings) >= 1

    def test_boundary_search_invalid_points_422(self, client: TestClient):
        # Less than 3 points
        resp = client.post(
            "/listings/search-boundary",
            json={"polygon": [[21.1702, 72.8311], [21.1800, 72.8400]]},
        )
        assert resp.status_code == 422

    def test_boundary_search_exceeds_max_vertices_422(self, client: TestClient):
        # More than 1000 points (same limit as ai.rag.boundary_filter)
        huge_polygon = [[21.17 + i*0.00001, 72.83 + i*0.00001] for i in range(1001)]
        resp = client.post(
            "/listings/search-boundary",
            json={"polygon": huge_polygon},
        )
        assert resp.status_code == 422

    def test_boundary_excludes_outside_points(self, client: TestClient):
        token = register_broker(client, email="boundary_out@test.com")["access_token"]
        inside = client.post(
            "/listings", json=listing_payload(title="Inside"), headers=auth_header(token)
        ).json()["id"]
        outside = client.post(
            "/listings",
            json=listing_payload(title="Outside", lat=21.1418, lng=72.7709),  # Vesu
            headers=auth_header(token),
        ).json()["id"]
        ids = [l["id"] for l in client.post(
            "/listings/search-boundary", json={"polygon": ADAJAN_POLYGON}
        ).json()]
        assert inside in ids
        assert outside not in ids

    def test_self_crossing_polygon_is_repaired_not_rejected(self, client: TestClient):
        """A figure-8 (bow-tie) is repaired with ST_MakeValid, as the AI module does."""
        token = register_broker(client, email="bowtie@test.com")["access_token"]
        listing_id = client.post(
            "/listings", json=listing_payload(title="In left lobe"), headers=auth_header(token)
        ).json()["id"]
        # Bow-tie crossing at (21.1702, 72.8400); left lobe contains the Adajan point
        bowtie = [
            [21.1800, 72.8200],
            [21.1600, 72.8600],
            [21.1800, 72.8600],
            [21.1600, 72.8200],
        ]
        resp = client.post("/listings/search-boundary", json={"polygon": bowtie})
        assert resp.status_code == 200
        assert listing_id in [l["id"] for l in resp.json()]

    def test_boundary_uses_ai_get_candidates_when_installed(self, client: TestClient, fake_ai):
        token = register_broker(client, email="ai_boundary@test.com")["access_token"]
        listing_id = client.post(
            "/listings", json=listing_payload(), headers=auth_header(token)
        ).json()["id"]
        fake_ai["candidates"] = [listing_id]
        resp = client.post("/listings/search-boundary", json={"polygon": ADAJAN_POLYGON})
        assert [l["id"] for l in resp.json()] == [listing_id]
        assert fake_ai["get_candidates"][0] == fake_ai["get_candidates"][-1]
