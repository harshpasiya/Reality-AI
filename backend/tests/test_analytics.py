"""Tests for broker analytics endpoint — GET /brokers/{id}/analytics."""

import pytest
from fastapi.testclient import TestClient

from tests.conftest import register_broker, auth_header, listing_payload


class TestAnalytics:
    """GET /brokers/{id}/analytics."""

    def test_get_analytics_own_account(self, client: TestClient):
        token_resp = register_broker(client, email="analytics_broker@test.com")
        token = token_resp["access_token"]

        # First decode user_id or create a listing to get broker id
        listing_resp = client.post(
            "/listings",
            json=listing_payload(title="Broker Listing for Analytics", price=3500000),
            headers=auth_header(token),
        )
        broker_id = listing_resp.json()["broker_id"]

        resp = client.get(
            f"/brokers/{broker_id}/analytics",
            headers=auth_header(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_listings"] >= 1
        assert "total_leads" in data
        assert "total_views" in data
        assert "listings_breakdown" in data

    def test_get_analytics_other_broker_forbidden_403(self, client: TestClient):
        b1_token = register_broker(client, email="b1@test.com")["access_token"]
        b2_token = register_broker(client, email="b2@test.com")["access_token"]

        # Broker 1 creates a listing
        l_resp = client.post(
            "/listings",
            json=listing_payload(title="B1 Flat", price=3000000),
            headers=auth_header(b1_token),
        )
        b1_id = l_resp.json()["broker_id"]

        # Broker 2 tries to access Broker 1's analytics -> 403 Forbidden
        resp = client.get(
            f"/brokers/{b1_id}/analytics",
            headers=auth_header(b2_token),
        )
        assert resp.status_code == 403
