"""Public broker profile and localities — the pages a visitor sees without logging in."""

from tests.conftest import auth_header, listing_payload, register_broker, unique_email


def _broker_with_listings(client, statuses):
    broker = register_broker(client, email=unique_email("pub"), phone="+919876543210")
    token = broker["access_token"]
    ids = []
    for i, status in enumerate(statuses):
        resp = client.post("/listings", json=listing_payload(title=f"Flat number {i}"),
                           headers=auth_header(token))
        assert resp.status_code == 201, resp.text
        listing_id = resp.json()["id"]
        if status != "available":
            client.patch(f"/listings/{listing_id}/status", json={"status": status},
                         headers=auth_header(token))
        ids.append(listing_id)
    return broker, ids


class TestPublicProfile:
    def test_shows_only_visible_listings_without_login(self, client):
        broker, ids = _broker_with_listings(client, ["available", "under_offer", "sold"])
        resp = client.get(f"/brokers/{broker['user']['id']}/public")
        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "Test Broker"
        assert body["active_listings"] == 2
        assert {l["id"] for l in body["listings"]} == set(ids[:2])

    def test_never_exposes_contact_details(self, client):
        broker, _ = _broker_with_listings(client, ["available"])
        body = client.get(f"/brokers/{broker['user']['id']}/public").json()
        assert "phone" not in body and "email" not in body

    def test_unknown_broker_404(self, client):
        assert client.get("/brokers/999999999/public").status_code == 404


def test_localities_sorted_with_coordinates(client):
    resp = client.get("/localities")
    assert resp.status_code == 200
    names = [l["name"] for l in resp.json()]
    assert names == sorted(names) and "Vesu" in names and len(names) == 20
    vesu = next(l for l in resp.json() if l["name"] == "Vesu")
    assert (vesu["lat"], vesu["lng"], vesu["radius_m"]) == (21.1545, 72.7757, 2000)
