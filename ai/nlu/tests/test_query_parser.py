"""Tests for ai.nlu.query_parser — rules path and merge logic, with a fake model (no GPU)."""

from __future__ import annotations

import json

import pytest

import ai.inference.load_model as load_model
from ai.nlu import query_parser
from ai.nlu.query_parser import merge, parse_query
from ai.nlu.schema import ParsedQuery

L, CR = 1_00_000, 1_00_00_000


def _model_json(**fields) -> str:
    base = {"is_property_query": True, "bhk": None, "locality": None, "price_min": None,
            "price_max": None, "property_type": None, "keywords": []}
    base.update(fields)
    return json.dumps(base)


@pytest.fixture(autouse=True)
def _fresh_cache():
    query_parser.cache_clear()
    yield
    query_parser.cache_clear()


@pytest.fixture
def fake_model(monkeypatch):
    """Pretend the model is available; tests set .output to control what it 'generates'."""
    class Fake:
        output = _model_json()
        calls = 0

    def generate(query: str) -> str:
        Fake.calls += 1
        return Fake.output

    monkeypatch.setattr(load_model, "is_model_available", lambda: True)
    monkeypatch.setattr(query_parser, "_generate", generate)
    monkeypatch.setenv("NLU_BACKEND", "hybrid")
    return Fake


# ── rules backend ──────────────────────────────────────────────────────────

def test_rules_backend_never_calls_model(monkeypatch, fake_model) -> None:
    monkeypatch.setenv("NLU_BACKEND", "rules")
    pq = parse_query("3bhk in vesu under 80 lakh")
    assert (pq.source, pq.bhk, pq.locality, pq.price_max) == ("rules", 3, "Vesu", 80 * L)
    assert fake_model.calls == 0


@pytest.mark.parametrize("query", ["", "   ", None])
def test_empty_input(query) -> None:
    assert parse_query(query) == ParsedQuery(is_property_query=False, source="rules")


def test_long_input_truncated(monkeypatch) -> None:
    monkeypatch.setenv("NLU_BACKEND", "rules")
    pq = parse_query("2bhk in adajan " + "x" * 5000)
    assert pq.bhk == 2 and pq.locality == "Adajan"


def test_unknown_backend_falls_back_to_hybrid(monkeypatch, fake_model) -> None:
    monkeypatch.setenv("NLU_BACKEND", "banana")
    assert parse_query("2bhk vesu").source == "hybrid"


# ── model unavailable / invalid ────────────────────────────────────────────

def test_model_unavailable_uses_rules(monkeypatch) -> None:
    monkeypatch.setenv("NLU_BACKEND", "hybrid")
    monkeypatch.setattr(load_model, "is_model_available", lambda: False)
    pq = parse_query("3bhk in vesu")
    assert pq.source == "rules" and pq.bhk == 3


def test_model_load_failure_falls_back_and_is_not_retried(monkeypatch) -> None:
    monkeypatch.setenv("NLU_BACKEND", "hybrid")
    monkeypatch.setattr(load_model, "is_model_available", lambda: True)
    calls = []

    def boom(query):
        calls.append(query)
        raise load_model.ModelUnavailableError("CUDA out of memory")

    monkeypatch.setattr(query_parser, "_generate", boom)
    assert parse_query("3bhk in vesu").source == "rules"
    assert parse_query("2bhk in pal").source == "rules"
    assert len(calls) == 1  # the failed load is remembered


def test_generation_error_falls_back(monkeypatch, fake_model) -> None:
    monkeypatch.setattr(query_parser, "_generate", lambda q: (_ for _ in ()).throw(RuntimeError("x")))
    assert parse_query("3bhk in vesu").source == "rules"


@pytest.mark.parametrize("raw", ["not json at all", '{"bhk": 3}', '{"is_property_query": true, "bhk": "3"'])
def test_invalid_model_output_uses_rules(fake_model, raw) -> None:
    fake_model.output = raw
    pq = parse_query("3bhk in vesu")
    assert pq.source == "rules" and pq.bhk == 3


# ── merge logic ────────────────────────────────────────────────────────────

def test_hybrid_takes_fields_from_model(fake_model) -> None:
    fake_model.output = _model_json(bhk=3, locality="Piplod", property_type="flat", keywords=["gym"])
    pq = parse_query("3bhk appartment in pipload with gymancium")  # typos the rules miss
    assert (pq.source, pq.bhk, pq.locality, pq.property_type, pq.keywords) == \
        ("hybrid", 3, "Piplod", "flat", ("gym",))


def test_hybrid_prefers_rules_prices(fake_model) -> None:
    # The model got the arithmetic wrong; rules found the price, so rules win.
    fake_model.output = _model_json(bhk=2, price_max={"amount": 8, "unit": "lakh"})
    pq = parse_query("2bhk under 80 lakh")
    assert pq.price_max == 80 * L and pq.price_min is None


def test_hybrid_uses_model_price_when_rules_found_none(fake_model) -> None:
    fake_model.output = _model_json(price_max={"amount": 70, "unit": "lakh"})
    pq = parse_query("flat under 70 laks")  # "laks" isn't a unit the rules know
    assert pq.price_max == 70 * L


def test_model_offtopic_wins_over_weak_rules_signal(fake_model) -> None:
    fake_model.output = _model_json(is_property_query=False)
    pq = parse_query("best vegetarian restaurants in vesu")
    assert pq == ParsedQuery(is_property_query=False, source="hybrid")


def test_rules_override_model_offtopic_with_two_signals(fake_model) -> None:
    fake_model.output = _model_json(is_property_query=False)
    pq = parse_query("3bhk flat in vesu")
    assert pq.is_property_query and pq.source == "hybrid" and pq.bhk == 3 and pq.locality == "Vesu"


def test_model_backend_skips_merge(monkeypatch, fake_model) -> None:
    monkeypatch.setenv("NLU_BACKEND", "model")
    fake_model.output = _model_json(bhk=2, price_max={"amount": 8, "unit": "lakh"})
    pq = parse_query("2bhk under 80 lakh")
    assert pq.source == "model" and pq.price_max == 8 * L  # the model's own (wrong) price


def test_merge_function_directly() -> None:
    rules = ParsedQuery(True, bhk=2, price_min=50 * L, source="rules")
    model = ParsedQuery(True, bhk=3, locality="Vesu", keywords=("lift",), source="model")
    assert merge(rules, model) == ParsedQuery(True, 3, "Vesu", 50 * L, None, None, ("lift",), "hybrid")


def test_hybrid_fills_model_gaps_from_rules(fake_model) -> None:
    # Eval-set failure: the 4B model left locality empty on a Hinglish query.
    fake_model.output = _model_json(bhk=2, property_type="flat")
    pq = parse_query("rander me 2bhk flat dikhao")
    assert (pq.bhk, pq.locality, pq.property_type) == (2, "Rander", "flat")


def test_hybrid_unions_keywords(fake_model) -> None:
    # Eval-set failure: the model missed "new construction"; rules found it.
    fake_model.output = _model_json(locality="Varachha", property_type="flat", keywords=["parking"])
    pq = parse_query("varachha me new construction flat with parking 45 lakh tak")
    assert set(pq.keywords) == {"parking", "new construction"}
    assert pq.keywords[0] == "parking"  # model's keywords first, no duplicates
    assert len(pq.keywords) == len(set(pq.keywords))


def test_hybrid_drops_hallucinated_locality(fake_model) -> None:
    # Kaggle val failure: "batavo" (Gujarati for "show") read as Bhatar.
    fake_model.output = _model_json(locality="Bhatar", property_type="house_land")
    pq = parse_query("villas batavo")
    assert pq.locality is None and pq.property_type == "house_land"


def test_hybrid_keeps_misspelled_but_grounded_locality(fake_model) -> None:
    fake_model.output = _model_json(locality="Jahangirpura")
    assert parse_query("1bhk in jhangirpura").locality == "Jahangirpura"


# ── caching ────────────────────────────────────────────────────────────────

def test_cache_runs_model_once_per_query(fake_model) -> None:
    for _ in range(3):
        parse_query("  2bhk in vesu  ")
    parse_query("2bhk in vesu")
    assert fake_model.calls == 1


def test_cache_is_per_backend(monkeypatch, fake_model) -> None:
    parse_query("2bhk in vesu")
    monkeypatch.setenv("NLU_BACKEND", "rules")
    assert parse_query("2bhk in vesu").source == "rules"
