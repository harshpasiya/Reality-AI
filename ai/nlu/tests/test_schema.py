"""Tests for ai.nlu.schema."""

from __future__ import annotations

import json

import pytest

from ai.nlu.schema import (
    MODEL_OUTPUT_KEYS,
    ParsedQuery,
    RawPrice,
    dump_model_output,
    extract_first_json,
    to_rupees,
    validate_model_output,
)


def _obj(**overrides) -> dict:
    base = {
        "is_property_query": True,
        "bhk": 3,
        "locality": "Vesu",
        "price_min": None,
        "price_max": {"amount": 80, "unit": "lakh"},
        "property_type": "flat",
        "keywords": ["gym"],
    }
    base.update(overrides)
    return base


def test_to_rupees() -> None:
    assert to_rupees(RawPrice(80, "lakh")) == 8_000_000
    assert to_rupees({"amount": 0.8, "unit": "crore"}) == 8_000_000
    assert to_rupees(RawPrice(4_500_000, "rupee")) == 4_500_000
    with pytest.raises(ValueError):
        to_rupees({"amount": 1, "unit": "dollar"})


def test_valid_output() -> None:
    pq = validate_model_output(_obj())
    assert pq == ParsedQuery(True, 3, "Vesu", None, 8_000_000.0, "flat", ("gym",), "model")


def test_missing_optional_keys_are_null() -> None:
    pq = validate_model_output({"is_property_query": True, "bhk": 2})
    assert pq is not None and pq.bhk == 2 and pq.locality is None and pq.keywords == ()


def test_missing_is_property_query_is_invalid() -> None:
    assert validate_model_output({"bhk": 2}) is None


@pytest.mark.parametrize(
    "bad",
    [
        {"is_property_query": "yes"},
        _obj(bhk="three"),
        _obj(bhk=True),
        _obj(locality=5),
        _obj(property_type=["flat"]),
        _obj(keywords="gym"),
        _obj(keywords=[1, 2]),
    ],
)
def test_wrong_types_are_invalid(bad: dict) -> None:
    assert validate_model_output(bad) is None


def test_not_a_dict() -> None:
    assert validate_model_output(["is_property_query"]) is None
    assert validate_model_output(None) is None


def test_hallucinated_locality_dropped() -> None:
    pq = validate_model_output(_obj(locality="Bandra West"))
    assert pq is not None and pq.locality is None and pq.bhk == 3


def test_locality_alias_canonicalized() -> None:
    assert validate_model_output(_obj(locality="city light")).locality == "Citylight"


@pytest.mark.parametrize("bhk", [0, 25, -1])
def test_out_of_range_bhk_dropped(bhk: int) -> None:
    pq = validate_model_output(_obj(bhk=bhk))
    assert pq is not None and pq.bhk is None and pq.locality == "Vesu"


def test_float_bhk_accepted_when_integral() -> None:
    assert validate_model_output(_obj(bhk=2.0)).bhk == 2


def test_unknown_property_type_dropped() -> None:
    assert validate_model_output(_obj(property_type="office")).property_type is None


def test_inverted_price_range_drops_both() -> None:
    pq = validate_model_output(
        _obj(price_min={"amount": 1, "unit": "crore"}, price_max={"amount": 50, "unit": "lakh"})
    )
    assert pq.price_min is None and pq.price_max is None


def test_mixed_unit_range_ok() -> None:
    pq = validate_model_output(
        _obj(price_min={"amount": 80, "unit": "lakh"}, price_max={"amount": 1.2, "unit": "crore"})
    )
    assert (pq.price_min, pq.price_max) == (8_000_000, 12_000_000)


@pytest.mark.parametrize(
    "bad_price",
    [{"amount": -5, "unit": "lakh"}, {"amount": 0, "unit": "lakh"},
     {"amount": 5, "unit": "dollar"}, {"amount": "80", "unit": "lakh"}, "80 lakh"],
)
def test_bad_price_drops_both(bad_price) -> None:
    pq = validate_model_output(_obj(price_min={"amount": 20, "unit": "lakh"}, price_max=bad_price))
    assert pq is not None and pq.price_min is None and pq.price_max is None


def test_keywords_synonyms_filter_and_dedup() -> None:
    pq = validate_model_output(_obj(keywords=["pool", "jacuzzi", "Gym", "gym", "swimming pool"]))
    assert pq.keywords == ("swimming pool", "gym")


def test_offtopic_forces_everything_empty() -> None:
    pq = validate_model_output(_obj(is_property_query=False))
    assert pq == ParsedQuery(is_property_query=False, source="model")
    assert pq.is_empty()


def test_extra_keys_ignored() -> None:
    assert validate_model_output(_obj(reasoning="because")) is not None


def test_extract_json_wrapped_in_prose() -> None:
    text = 'Sure! Here is the JSON:\n```json\n{"is_property_query": true, "bhk": 2}\n```\nDone.'
    assert extract_first_json(text) == {"is_property_query": True, "bhk": 2}


def test_extract_json_braces_inside_strings() -> None:
    assert extract_first_json('x {"locality": "a}b{c"} y') == {"locality": "a}b{c"}


def test_extract_json_truncated() -> None:
    assert extract_first_json('{"is_property_query": true, "bhk": 3, "locality": "Ve') is None


def test_extract_json_skips_invalid_then_finds_valid() -> None:
    assert extract_first_json("{not json} then {\"a\": 1}") == {"a": 1}


def test_extract_json_none_and_empty() -> None:
    assert extract_first_json("") is None
    assert extract_first_json("no json here") is None


def test_dump_model_output_key_order_and_ints() -> None:
    out = dump_model_output({"bhk": 3, "is_property_query": True,
                             "price_max": {"amount": 80.0, "unit": "lakh"}})
    assert list(json.loads(out)) == list(MODEL_OUTPUT_KEYS)
    assert '"amount":80,' in out and json.loads(out)["keywords"] == []


def test_describe_and_is_empty() -> None:
    pq = ParsedQuery(True, 3, "Vesu", None, 8_000_000.0, "flat", ())
    assert pq.describe() == "3 BHK flat in Vesu, up to Rs.80.0 L"
    both = ParsedQuery(True, None, None, 5_000_000.0, 12_000_000.0, "house_land", ("garden",))
    assert both.describe() == "house or plot, Rs.50.0 L to Rs.1.20 Cr, with garden"
    assert ParsedQuery(True).describe() == "property"
    assert ParsedQuery(True).is_empty()
    assert ParsedQuery(False).describe() == "not a property query"
