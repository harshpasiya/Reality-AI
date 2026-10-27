"""Tests for customer chat endpoint — POST /chat."""

import pytest
from fastapi.testclient import TestClient

from tests.conftest import auth_header


def register_customer(client: TestClient, email: str = "cust@test.com") -> dict:
    resp = client.post("/auth/register", json={
        "email": email,
        "password": "testpass123",
        "name": "Test Customer",
        "role": "customer",
    })
    return resp.json()


class TestChat:
    """POST /chat."""

    def test_chat_new_conversation(self, client: TestClient):
        token = register_customer(client)["access_token"]
        resp = client.post(
            "/chat",
            json={"message": "Looking for 2BHK flats in Adajan"},
            headers=auth_header(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "reply" in data
        assert "listings" in data
        assert "conversation_id" in data
        assert isinstance(data["conversation_id"], int)
        assert "[PLACEHOLDER MODE]" in data["reply"]

    def test_chat_unauthenticated_401(self, client: TestClient):
        resp = client.post(
            "/chat",
            json={"message": "Looking for properties"},
        )
        assert resp.status_code == 401

    def test_chat_broker_forbidden_403(self, client: TestClient):
        from tests.conftest import register_broker
        token = register_broker(client, email="broker_chat@test.com")["access_token"]
        resp = client.post(
            "/chat",
            json={"message": "Looking for properties"},
            headers=auth_header(token),
        )
        assert resp.status_code == 403
        assert "Only customers" in resp.json()["detail"]

    def test_chat_history_retrieval(self, client: TestClient):
        token = register_customer(client, email="cust_hist@test.com")["access_token"]
        post_resp = client.post(
            "/chat",
            json={"message": "Find 3BHK flats in Vesu"},
            headers=auth_header(token),
        )
        assert post_resp.status_code == 200
        conv_id = post_resp.json()["conversation_id"]

        hist_resp = client.get(
            f"/chat/{conv_id}",
            headers=auth_header(token),
        )
        assert hist_resp.status_code == 200
        hist_data = hist_resp.json()
        assert hist_data["conversation_id"] == conv_id
        assert len(hist_data["messages"]) >= 2
        assert "listings" in hist_data
