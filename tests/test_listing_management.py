"""Listing rules and broker management: rooms, status, edit, withdraw, photos."""

import struct
import zlib

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.conftest import (
    ADAJAN,
    auth_header,
    create_listing,
    listing_payload,
    register_broker,
    register_customer,
    unique_email,
)

VESU = {"lat": 21.1418, "lng": 72.7709}


def _png_bytes() -> bytes:
    """A valid 1x1 PNG."""
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    idat = zlib.compress(b"\x00\xff\x00\x00")
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


class TestListingRules:
    def test_flat_without_bedrooms_422(self, client: TestClient):
        token = register_broker(client, email=unique_email("rooms"))["access_token"]
        resp = client.post("/listings", json=listing_payload(rooms=None), headers=auth_header(token))
        assert resp.status_code == 422

    def test_unknown_rooms_key_422(self, client: TestClient):
        token = register_broker(client, email=unique_email("roomkey"))["access_token"]
        resp = client.post(
            "/listings", json=listing_payload(rooms={"bedroom": 2}), headers=auth_header(token)
        )
        assert resp.status_code == 422

    def test_open_plot_may_have_no_rooms(self, client: TestClient, db_session: Session):
        token = register_broker(client, email=unique_email("plot"))["access_token"]
        listing = create_listing(
            client, token, property_type="house_land", rooms=None, plot_area=2400, carpet_area=None
        )
        assert listing["rooms"] is None
        assert listing["status"] == "available"
        # stored as SQL NULL (not the JSON value 'null'), so "rooms IS NULL" works
        assert db_session.execute(
            text("SELECT rooms IS NULL FROM listing WHERE id = :id"), {"id": listing["id"]}
        ).scalar() is True

    def test_client_cannot_set_amenities(self, client: TestClient):
        token = register_broker(client, email=unique_email("amen"))["access_token"]
        resp = client.post(
            "/listings",
            json=listing_payload(amenities={"schools": []}),
            headers=auth_header(token),
        )
        assert resp.status_code == 422

    def test_search_rejects_unknown_property_type(self, client: TestClient):
        resp = client.get("/listings/search", params={**ADAJAN, "radius_km": 2, "property_type": "villa"})
        assert resp.status_code == 422

    def test_search_rejects_price_min_above_max(self, client: TestClient):
        resp = client.get(
            "/listings/search",
            params={**ADAJAN, "radius_km": 2, "price_min": 9000000, "price_max": 1000000},
        )
        assert resp.status_code == 422


class TestStatus:
    def test_sold_listing_hidden_from_search_but_fetchable(self, client: TestClient):
        token = register_broker(client, email=unique_email("sold"))["access_token"]
        listing_id = create_listing(client, token)["id"]
        resp = client.patch(
            f"/listings/{listing_id}/status", json={"status": "sold"}, headers=auth_header(token)
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "sold"

        radius = client.get("/listings/search", params={**ADAJAN, "radius_km": 1, "limit": 100}).json()
        assert listing_id not in [l["id"] for l in radius]

        polygon = [[21.16, 72.82], [21.18, 72.82], [21.18, 72.84], [21.16, 72.84]]
        boundary = client.post("/listings/search-boundary", json={"polygon": polygon}).json()
        assert listing_id not in [l["id"] for l in boundary]

        assert client.get(f"/listings/{listing_id}").json()["status"] == "sold"

    def test_under_offer_stays_visible(self, client: TestClient):
        token = register_broker(client, email=unique_email("offer"))["access_token"]
        listing_id = create_listing(client, token)["id"]
        client.patch(
            f"/listings/{listing_id}/status", json={"status": "under_offer"}, headers=auth_header(token)
        )
        radius = client.get("/listings/search", params={**ADAJAN, "radius_km": 1, "limit": 100}).json()
        assert listing_id in [l["id"] for l in radius]

    def test_invalid_status_422(self, client: TestClient):
        token = register_broker(client, email=unique_email("badstatus"))["access_token"]
        listing_id = create_listing(client, token)["id"]
        resp = client.patch(
            f"/listings/{listing_id}/status", json={"status": "gone"}, headers=auth_header(token)
        )
        assert resp.status_code == 422

    def test_delete_withdraws(self, client: TestClient):
        token = register_broker(client, email=unique_email("withdraw"))["access_token"]
        listing_id = create_listing(client, token)["id"]
        assert client.delete(f"/listings/{listing_id}", headers=auth_header(token)).status_code == 204
        assert client.get(f"/listings/{listing_id}").json()["status"] == "withdrawn"


class TestEdit:
    def test_other_broker_403(self, client: TestClient):
        owner = register_broker(client, email=unique_email("owner"))["access_token"]
        other = register_broker(client, email=unique_email("other"))["access_token"]
        listing_id = create_listing(client, owner)["id"]
        resp = client.patch(f"/listings/{listing_id}", json={"title": "Mine now"}, headers=auth_header(other))
        assert resp.status_code == 403

    def test_customer_403(self, client: TestClient):
        owner = register_broker(client, email=unique_email("owner2"))["access_token"]
        customer = register_customer(client, email=unique_email("cust_edit"))["access_token"]
        listing_id = create_listing(client, owner)["id"]
        resp = client.patch(f"/listings/{listing_id}", json={"title": "x"}, headers=auth_header(customer))
        assert resp.status_code == 403

    def test_title_edit_reembeds_and_bumps_updated_at(self, client: TestClient, fake_ai):
        token = register_broker(client, email=unique_email("edit"))["access_token"]
        created = create_listing(client, token)
        listing_id = created["id"]
        fake_ai["embed_single"].clear()

        resp = client.patch(
            f"/listings/{listing_id}",
            json={"title": "3 BHK penthouse with terrace"},
            headers=auth_header(token),
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "3 BHK penthouse with terrace"
        assert resp.json()["updated_at"] >= created["updated_at"]
        assert fake_ai["embed_single"] == [listing_id]
        assert fake_ai["fetch_and_cache"][-1] == (listing_id, False)  # only from create

    def test_location_edit_refetches_amenities_with_force(self, client: TestClient, fake_ai):
        token = register_broker(client, email=unique_email("move"))["access_token"]
        listing_id = create_listing(client, token)["id"]
        fake_ai["embed_single"].clear()
        resp = client.patch(f"/listings/{listing_id}", json=VESU, headers=auth_header(token))
        assert resp.status_code == 200
        assert (resp.json()["lat"], resp.json()["lng"]) == (VESU["lat"], VESU["lng"])
        assert fake_ai["fetch_and_cache"][-1] == (listing_id, True)
        assert fake_ai["embed_single"] == []  # fetch_and_cache re-embeds itself

    def test_area_edit_does_not_reembed(self, client: TestClient, fake_ai):
        token = register_broker(client, email=unique_email("area"))["access_token"]
        listing_id = create_listing(client, token)["id"]
        fake_ai["embed_single"].clear()
        client.patch(f"/listings/{listing_id}", json={"carpet_area": 950}, headers=auth_header(token))
        assert fake_ai["embed_single"] == []

    def test_lat_without_lng_422(self, client: TestClient):
        token = register_broker(client, email=unique_email("latonly"))["access_token"]
        listing_id = create_listing(client, token)["id"]
        resp = client.patch(f"/listings/{listing_id}", json={"lat": 21.15}, headers=auth_header(token))
        assert resp.status_code == 422

    def test_removing_flat_bedrooms_422(self, client: TestClient):
        token = register_broker(client, email=unique_email("norooms"))["access_token"]
        listing_id = create_listing(client, token)["id"]
        resp = client.patch(f"/listings/{listing_id}", json={"rooms": None}, headers=auth_header(token))
        assert resp.status_code == 422


class TestImages:
    def test_upload_png(self, client: TestClient, tmp_path, monkeypatch):
        monkeypatch.setattr("app.core.config.settings.UPLOAD_DIR", str(tmp_path))
        token = register_broker(client, email=unique_email("img"))["access_token"]
        listing_id = create_listing(client, token)["id"]
        resp = client.post(
            f"/listings/{listing_id}/images",
            files={"file": ("photo.png", _png_bytes(), "image/png")},
            headers=auth_header(token),
        )
        assert resp.status_code == 201, resp.text
        images = resp.json()["images"]
        assert len(images) == 1 and images[0]["order"] == 0
        assert images[0]["url"].startswith(f"/uploads/{listing_id}/")
        assert any(tmp_path.joinpath(str(listing_id)).iterdir())

    def test_non_image_rejected(self, client: TestClient, tmp_path, monkeypatch):
        monkeypatch.setattr("app.core.config.settings.UPLOAD_DIR", str(tmp_path))
        token = register_broker(client, email=unique_email("notimg"))["access_token"]
        listing_id = create_listing(client, token)["id"]
        resp = client.post(
            f"/listings/{listing_id}/images",
            files={"file": ("evil.png", b"<script>alert(1)</script>", "image/png")},
            headers=auth_header(token),
        )
        assert resp.status_code == 415

    def test_too_large_rejected(self, client: TestClient, tmp_path, monkeypatch):
        monkeypatch.setattr("app.core.config.settings.UPLOAD_DIR", str(tmp_path))
        token = register_broker(client, email=unique_email("bigimg"))["access_token"]
        listing_id = create_listing(client, token)["id"]
        big = _png_bytes() + b"\x00" * (5 * 1024 * 1024)
        resp = client.post(
            f"/listings/{listing_id}/images",
            files={"file": ("big.png", big, "image/png")},
            headers=auth_header(token),
        )
        assert resp.status_code == 413


class TestBrokerListings:
    def test_lists_own_listings_with_counts(self, client: TestClient):
        reg = register_broker(client, email=unique_email("dash"))
        token, broker_id = reg["access_token"], reg["user"]["id"]
        listing_id = create_listing(client, token)["id"]
        client.patch(f"/listings/{listing_id}/status", json={"status": "sold"}, headers=auth_header(token))
        client.get(f"/listings/{listing_id}")  # one view

        resp = client.get(f"/brokers/{broker_id}/listings", headers=auth_header(token))
        assert resp.status_code == 200
        [item] = resp.json()
        assert item["status"] == "sold" and item["view_count"] == 1 and item["lead_count"] == 0

        assert client.get(
            f"/brokers/{broker_id}/listings", params={"status": "available"}, headers=auth_header(token)
        ).json() == []

    def test_other_broker_403(self, client: TestClient):
        a = register_broker(client, email=unique_email("dash_a"))
        b = register_broker(client, email=unique_email("dash_b"))
        resp = client.get(f"/brokers/{a['user']['id']}/listings", headers=auth_header(b["access_token"]))
        assert resp.status_code == 403
