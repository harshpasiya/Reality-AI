"""Tests for the templated generate_response() (rules backend, no model)."""

from __future__ import annotations

import importlib

import pytest

from ai.inference.generate_response import generate_response

# ai/inference/__init__.py re-exports the *function* generate_response, which
# shadows the submodule name on the package — import the module explicitly.
gr_module = importlib.import_module("ai.inference.generate_response")
from ai.nlu import query_parser

L = 1_00_000


@pytest.fixture(autouse=True)
def _rules_backend(monkeypatch):
    monkeypatch.setenv("NLU_BACKEND", "rules")
    query_parser.cache_clear()
    yield
    query_parser.cache_clear()


def _listing(i: int, **kw) -> dict:
    base = {"id": i, "title": f"Spacious 3BHK in Vesu #{i}", "description": "...", "price": 75 * L,
            "property_type": "flat", "bhk": 3, "lat": 21.15, "lng": 72.77, "amenities": None,
            "distance_score": 0.5, "match_note": "exact"}
    base.update(kw)
    return base


def test_offtopic_gets_a_deterministic_redirect() -> None:
    a = generate_response("what's the weather today?", [], None)
    b = generate_response("What's the weather today?  ", [], None)
    assert a == b and a in gr_module._REDIRECTS


def test_redirect_ignores_listings_for_offtopic() -> None:
    assert generate_response("tell me a joke", [_listing(1)], None) in gr_module._REDIRECTS


def test_results_reply_lists_only_given_listings() -> None:
    listings = [_listing(1), _listing(2, price=1.2 * 1_00_00_000, bhk=None, property_type="house_land")]
    reply = generate_response("3bhk flat in vesu under 80 lakh", listings, None)
    assert reply.splitlines()[0] == "Here are 2 properties matching 3 BHK flat in Vesu, up to Rs.80.0 L:"
    assert "1. Spacious 3BHK in Vesu #1 — Rs.75.0 L, flat, 3 BHK" in reply
    assert "2. Spacious 3BHK in Vesu #2 — Rs.1.20 Cr, house/plot" in reply
    assert "#3" not in reply


def test_at_most_five_listings() -> None:
    reply = generate_response("3bhk in vesu", [_listing(i) for i in range(1, 9)], None)
    assert "5. " in reply and "6. " not in reply


def test_singular_wording() -> None:
    assert generate_response("3bhk in vesu", [_listing(1)], None).startswith("Here is 1 property matching")


@pytest.mark.parametrize(("note", "expected"), [
    ("relaxed_radius", "I couldn't find exact matches in Vesu, so I included nearby areas."),
    ("relaxed_bhk", "I couldn't find a 3 BHK in or near Vesu, so I've included other sizes."),
    ("relaxed_locality", "Nothing matched in or near Vesu, so these are from other parts of Surat."),
])
def test_relaxation_is_stated_honestly(note: str, expected: str) -> None:
    reply = generate_response("3bhk in vesu", [_listing(1, match_note=note)], None)
    assert expected in reply and "close to what you asked for" in reply.splitlines()[0]


def test_no_results_with_budget_mentions_budget() -> None:
    reply = generate_response("3bhk in vesu under 20 lakh", [], None)
    assert "3 BHK property in Vesu, up to Rs.20.0 L" in reply
    assert "within that budget" in reply and "raising it" in reply


def test_no_results_without_budget_suggests_dropping_bhk() -> None:
    assert "without the 3 BHK requirement" in generate_response("3bhk in vesu", [], None)


def test_no_results_no_filters() -> None:
    assert "locality, a budget or the number of bedrooms" in generate_response("show me properties", [], None)


def test_amenities_only_when_asked() -> None:
    amenities = {"schools": [{"name": "Sunrise School", "distance_m": 450, "rating": 4.3,
                              "user_ratings_total": 120}], "parks": []}
    listings = [_listing(1, amenities=amenities), _listing(2)]
    plain = generate_response("3bhk in vesu", listings, None)
    assert "Nearby" not in plain and "amenities" not in plain.lower()
    asked = generate_response("3bhk in vesu near a good school", listings, None)
    assert "Nearby: Schools: Sunrise School · 4.3★ (120 reviews) · 450m" in asked
    assert "isn't available for this listing yet" in asked


def test_amenities_as_json_string() -> None:
    listing = _listing(1, amenities='{"parks": [{"name": "Green Park", "distance_m": 600, "rating": null}]}')
    assert "Parks: Green Park · 600m" in generate_response("flats near a park in vesu", [listing], None)


def test_never_raises(monkeypatch) -> None:
    monkeypatch.setattr(gr_module, "parse_query", lambda q: (_ for _ in ()).throw(RuntimeError("boom")))
    assert generate_response("3bhk", [], None) == gr_module._FALLBACK_REPLY


def test_handles_none_inputs() -> None:
    assert generate_response(None, None, None) in gr_module._REDIRECTS  # type: ignore[arg-type]
