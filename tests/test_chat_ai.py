"""POST /chat against stand-in AI modules with the real return shapes (fake_ai)."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.conversation import Conversation
from app.models.lead import Lead
from app.models.listing import Listing
from tests.conftest import (
    auth_header,
    create_listing,
    register_broker,
    register_customer,
    unique_email,
)


def _setup(client: TestClient, n_listings: int = 2):
    broker = register_broker(client, email=unique_email("chat_ai_broker"))["access_token"]
    ids = [create_listing(client, broker, title=f"Flat {i}")["id"] for i in range(n_listings)]
    customer = register_customer(client, email=unique_email("chat_ai_cust"))
    return broker, ids, customer["access_token"], customer["user"]["id"]


class TestChatWithAI:
    def test_dict_results_returned_in_ai_order_with_match_note(self, client, fake_ai):
        _, (a, b), token, _ = _setup(client)
        fake_ai["results"] = [
            {"id": b, "title": "Flat 1", "bhk": 2, "match_note": "relaxed_radius", "distance_score": 0.4},
            {"id": a, "title": "Flat 0", "bhk": 2, "match_note": "exact", "distance_score": 0.2},
        ]
        resp = client.post("/chat", json={"message": "2 bhk in adajan"}, headers=auth_header(token))
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["reply"] == "2 properties"
        assert [l["id"] for l in data["listings"]] == [b, a]
        assert data["listings"][0]["match_note"] == "relaxed_radius"
        assert data["listings"][0]["bhk"] == 2
        assert data["listings"][1]["distance_score"] == 0.2

    def test_off_topic_returns_empty_and_creates_no_leads(self, client, fake_ai, db_session: Session):
        _, _, token, customer_id = _setup(client)
        fake_ai["results"] = []
        resp = client.post("/chat", json={"message": "what's the weather?"}, headers=auth_header(token))
        assert resp.status_code == 200
        assert resp.json()["listings"] == []
        assert db_session.query(Lead).filter(Lead.customer_id == customer_id).count() == 0

    def test_results_create_views_not_leads(self, client, fake_ai, db_session: Session):
        _, (a, b), token, customer_id = _setup(client)
        fake_ai["results"] = [{"id": a, "title": "Flat 0"}, {"id": b, "title": "Flat 1"}]
        client.post("/chat", json={"message": "flats"}, headers=auth_header(token))
        assert db_session.query(Lead).filter(Lead.customer_id == customer_id).count() == 0
        views = {l.id: l.view_count for l in db_session.query(Listing).filter(Listing.id.in_([a, b]))}
        assert views == {a: 1, b: 1}

    def test_retrieval_error_503_keeps_user_message(self, client, fake_ai, db_session: Session):
        _, _, token, customer_id = _setup(client, n_listings=0)
        fake_ai["search_error"] = fake_ai["RetrievalError"]("db down")
        resp = client.post("/chat", json={"message": "3 bhk in vesu"}, headers=auth_header(token))
        assert resp.status_code == 503
        conv = (
            db_session.query(Conversation)
            .filter(Conversation.customer_id == customer_id)
            .one()
        )
        assert [m["content"] for m in conv.messages] == ["3 bhk in vesu"]

    def test_value_error_from_search_is_422(self, client, fake_ai):
        _, _, token, _ = _setup(client, n_listings=0)
        fake_ai["search_error"] = ValueError("query must not be empty")
        resp = client.post("/chat", json={"message": "x"}, headers=auth_header(token))
        assert resp.status_code == 422

    def test_sold_listing_from_ai_is_dropped(self, client, fake_ai):
        broker, (a, b), token, _ = _setup(client)
        client.patch(f"/listings/{a}/status", json={"status": "sold"}, headers=auth_header(broker))
        fake_ai["results"] = [{"id": a, "title": "Flat 0"}, {"id": b, "title": "Flat 1"}]
        resp = client.post("/chat", json={"message": "flats"}, headers=auth_header(token))
        assert [l["id"] for l in resp.json()["listings"]] == [b]

    def test_polygon_goes_through_get_candidates(self, client, fake_ai):
        _, (a, _b), token, _ = _setup(client)
        fake_ai["candidates"] = [a]
        polygon = [[21.16, 72.82], [21.18, 72.82], [21.18, 72.84]]
        resp = client.post(
            "/chat", json={"message": "flats here", "polygon": polygon}, headers=auth_header(token)
        )
        assert resp.status_code == 200
        assert fake_ai["search"] == ("flats here", [a])
        assert fake_ai["get_candidates"][0] == fake_ai["get_candidates"][-1]  # ring closed

    def test_history_is_prior_turns_only(self, client, fake_ai):
        _, _, token, _ = _setup(client, n_listings=0)
        first = client.post("/chat", json={"message": "hello"}, headers=auth_header(token)).json()
        client.post(
            "/chat",
            json={"conversation_id": first["conversation_id"], "message": "2 bhk"},
            headers=auth_header(token),
        )
        assert [m["content"] for m in fake_ai["history"]] == ["hello", "0 properties"]
        assert set(fake_ai["history"][0]) == {"role", "content", "timestamp"}


class TestChatValidation:
    def test_polygon_with_two_points_422(self, client):
        token = register_customer(client, email=unique_email("poly2"))["access_token"]
        resp = client.post(
            "/chat",
            json={"message": "flats", "polygon": [[21.1, 72.8], [21.2, 72.9]]},
            headers=auth_header(token),
        )
        assert resp.status_code == 422

    def test_polygon_with_nan_422(self, client):
        token = register_customer(client, email=unique_email("polynan"))["access_token"]
        resp = client.post(
            "/chat",
            content='{"message": "flats", "polygon": [[21.1, 72.8], [NaN, 72.9], [21.2, 72.9]]}',
            headers={**auth_header(token), "Content-Type": "application/json"},
        )
        assert resp.status_code == 422

    def test_message_too_long_422(self, client):
        token = register_customer(client, email=unique_email("longmsg"))["access_token"]
        resp = client.post("/chat", json={"message": "a" * 1001}, headers=auth_header(token))
        assert resp.status_code == 422

    def test_placeholder_fallback_hides_sold_and_creates_no_leads(self, client, db_session: Session):
        broker = register_broker(client, email=unique_email("fb_broker"))["access_token"]
        sold = create_listing(client, broker, title="Sold flat")["id"]
        client.patch(f"/listings/{sold}/status", json={"status": "sold"}, headers=auth_header(broker))
        customer = register_customer(client, email=unique_email("fb_cust"))
        resp = client.post(
            "/chat", json={"message": "anything"}, headers=auth_header(customer["access_token"])
        )
        assert resp.status_code == 200
        assert sold not in [l["id"] for l in resp.json()["listings"]]
        assert db_session.query(Lead).filter(Lead.customer_id == customer["user"]["id"]).count() == 0


class TestBrokenAIPackage:
    """ai/ installed but failing at import (RuntimeError) must never cause a 500."""

    def test_chat_503_and_message_kept(self, client, broken_ai, db_session: Session):
        customer = register_customer(client, email=unique_email("broken_ai"))
        resp = client.post(
            "/chat", json={"message": "2 bhk in vesu"}, headers=auth_header(customer["access_token"])
        )
        assert resp.status_code == 503
        conv = (
            db_session.query(Conversation)
            .filter(Conversation.customer_id == customer["user"]["id"])
            .one()
        )
        assert conv.messages[0]["content"] == "2 bhk in vesu"

    def test_listing_still_created(self, client, broken_ai):
        token = register_broker(client, email=unique_email("broken_ai_b"))["access_token"]
        create_listing(client, token)

    def test_boundary_falls_back_to_backend_query(self, client, broken_ai):
        token = register_broker(client, email=unique_email("broken_ai_poly"))["access_token"]
        listing_id = create_listing(client, token)["id"]
        polygon = [[21.16, 72.82], [21.18, 72.82], [21.18, 72.84], [21.16, 72.84]]
        resp = client.post("/listings/search-boundary", json={"polygon": polygon})
        assert resp.status_code == 200
        assert listing_id in [l["id"] for l in resp.json()]
