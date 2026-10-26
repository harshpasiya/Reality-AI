"""Tests for ai.amenities.amenities_service failure handling — no network, no database."""

from __future__ import annotations

import pytest
import requests

from ai.amenities import amenities_service as svc

KEY = "AIzaTESTKEY0000000000000000000000000"


class RecordingEngine:
    """Records UPDATE statements; fetch_and_cache's reads are patched separately."""

    def __init__(self):
        self.writes = []

    def begin(self):
        engine = self

        class Conn:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def execute(self, sql, params):
                engine.writes.append((str(sql), params))

        return Conn()


@pytest.fixture
def engine(monkeypatch):
    eng = RecordingEngine()
    monkeypatch.setattr(svc, "_engine", eng)
    monkeypatch.setattr(svc, "_get_listing_location", lambda listing_id: (21.15, 72.77))
    monkeypatch.setattr(svc, "_get_existing_amenities", lambda listing_id: None)
    monkeypatch.setattr(svc.time, "sleep", lambda s: None)
    # Re-embedding is out of scope here.
    import ai.embeddings.embed_listings as el
    monkeypatch.setattr(el, "embed_single", lambda listing_id: None)
    return eng


def test_missing_api_key_writes_nothing(monkeypatch, engine) -> None:
    monkeypatch.delenv(svc._PLACES_API_KEY_ENV, raising=False)
    svc.fetch_and_cache(1)
    assert engine.writes == []


def test_failed_category_writes_nothing(monkeypatch, engine) -> None:
    monkeypatch.setenv(svc._PLACES_API_KEY_ENV, KEY)
    results = {"school": [], "hospital": None}  # hospitals failed, others empty
    monkeypatch.setattr(svc, "_fetch_category",
                        lambda lat, lng, place_type, api_key: results.get(place_type, []))
    svc.fetch_and_cache(1)
    assert engine.writes == []


def test_all_categories_ok_are_cached(monkeypatch, engine) -> None:
    monkeypatch.setenv(svc._PLACES_API_KEY_ENV, KEY)
    monkeypatch.setattr(svc, "_fetch_category", lambda lat, lng, place_type, api_key: [])
    svc.fetch_and_cache(1)
    assert len(engine.writes) == 1 and "UPDATE listings SET amenities" in engine.writes[0][0]


def test_api_key_is_redacted_from_logs(monkeypatch, caplog) -> None:
    monkeypatch.setattr(svc.time, "sleep", lambda s: None)

    def fail(*args, **kwargs):
        raise requests.ConnectionError(
            f"Max retries exceeded with url: /maps/api/place/nearbysearch/json?key={KEY}")

    monkeypatch.setattr(svc.requests, "get", fail)
    with caplog.at_level("WARNING"):
        assert svc._fetch_category(21.15, 72.77, "school", KEY) is None
    assert caplog.records and KEY not in caplog.text and "<redacted>" in caplog.text
