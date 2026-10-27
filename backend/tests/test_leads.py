"""Leads: explicit customer enquiries, broker inbox, follow-up status, phone reveal."""

from fastapi.testclient import TestClient

from tests.conftest import (
    auth_header,
    create_listing,
    register_broker,
    register_customer,
    unique_email,
)

PHONE = "+919876543210"


def _broker_with_listing(client: TestClient):
    reg = register_broker(client, email=unique_email("lead_broker"), phone=PHONE)
    listing = create_listing(client, reg["access_token"])
    return reg["access_token"], reg["user"]["id"], listing["id"]


class TestCreateLead:
    def test_customer_creates_one_lead_and_sees_phone(self, client: TestClient):
        _, _, listing_id = _broker_with_listing(client)
        token = register_customer(client, email=unique_email("lead_cust"))["access_token"]

        resp = client.post(
            f"/listings/{listing_id}/leads",
            json={"message": "Is parking included?"},
            headers=auth_header(token),
        )
        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["status"] == "new"
        assert data["message"] == "Is parking included?"
        assert data["broker"] == {"name": "Test Broker", "phone": PHONE}

        again = client.post(f"/listings/{listing_id}/leads", json={}, headers=auth_header(token))
        assert again.status_code == 409

    def test_phone_absent_from_public_listing(self, client: TestClient):
        _, _, listing_id = _broker_with_listing(client)
        body = client.get(f"/listings/{listing_id}").text
        assert PHONE not in body and "phone" not in body

    def test_broker_cannot_create_lead(self, client: TestClient):
        broker_token, _, listing_id = _broker_with_listing(client)
        resp = client.post(f"/listings/{listing_id}/leads", json={}, headers=auth_header(broker_token))
        assert resp.status_code == 403

    def test_sold_listing_409(self, client: TestClient):
        broker_token, _, listing_id = _broker_with_listing(client)
        client.patch(
            f"/listings/{listing_id}/status", json={"status": "sold"}, headers=auth_header(broker_token)
        )
        token = register_customer(client, email=unique_email("late"))["access_token"]
        resp = client.post(f"/listings/{listing_id}/leads", json={}, headers=auth_header(token))
        assert resp.status_code == 409

    def test_foreign_conversation_404(self, client: TestClient):
        _, _, listing_id = _broker_with_listing(client)
        owner = register_customer(client, email=unique_email("conv_owner"))["access_token"]
        conv_id = client.post("/chat", json={"message": "hi"}, headers=auth_header(owner)).json()["conversation_id"]
        other = register_customer(client, email=unique_email("conv_other"))["access_token"]
        resp = client.post(
            f"/listings/{listing_id}/leads",
            json={"conversation_id": conv_id},
            headers=auth_header(other),
        )
        assert resp.status_code == 404


class TestBrokerLeads:
    def test_inbox_status_update_and_analytics(self, client: TestClient):
        broker_token, broker_id, listing_id = _broker_with_listing(client)
        customer = register_customer(client, email=unique_email("inbox_cust"))
        lead_id = client.post(
            f"/listings/{listing_id}/leads",
            json={"message": "Visit on Sunday?"},
            headers=auth_header(customer["access_token"]),
        ).json()["id"]

        inbox = client.get(f"/brokers/{broker_id}/leads", headers=auth_header(broker_token))
        assert inbox.status_code == 200
        [item] = inbox.json()
        assert item["id"] == lead_id
        assert item["customer_email"] == customer["user"]["email"]
        assert item["listing_title"] == "Test Flat in Adajan"

        resp = client.patch(
            f"/leads/{lead_id}", json={"status": "visit_scheduled"}, headers=auth_header(broker_token)
        )
        assert resp.status_code == 200 and resp.json()["status"] == "visit_scheduled"

        analytics = client.get(f"/brokers/{broker_id}/analytics", headers=auth_header(broker_token)).json()
        assert analytics["total_leads"] == 1
        assert analytics["listings_breakdown"][0]["lead_count"] == 1

    def test_other_broker_cannot_update_lead(self, client: TestClient):
        _, _, listing_id = _broker_with_listing(client)
        customer = register_customer(client, email=unique_email("x_cust"))["access_token"]
        lead_id = client.post(
            f"/listings/{listing_id}/leads", json={}, headers=auth_header(customer)
        ).json()["id"]
        other = register_broker(client, email=unique_email("x_broker"))["access_token"]
        resp = client.patch(f"/leads/{lead_id}", json={"status": "closed"}, headers=auth_header(other))
        assert resp.status_code == 403

    def test_views_counted_in_analytics(self, client: TestClient):
        broker_token, broker_id, listing_id = _broker_with_listing(client)
        client.get(f"/listings/{listing_id}")
        client.get(f"/listings/{listing_id}")
        analytics = client.get(f"/brokers/{broker_id}/analytics", headers=auth_header(broker_token)).json()
        assert analytics["total_views"] == 2
        assert analytics["listings_breakdown"][0]["view_count"] == 2
