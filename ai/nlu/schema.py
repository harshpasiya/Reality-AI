"""The data contract for query understanding.

The fine-tuned model outputs one JSON object per query with the keys in
``MODEL_OUTPUT_KEYS``. Prices come out as ``{"amount": ..., "unit": ...}``
exactly as the user wrote them — small models are unreliable at arithmetic,
so conversion to rupees happens here in code (``to_rupees``), never in the
model.

``validate_model_output`` is the only path from raw model JSON to a
``ParsedQuery``, so everything downstream (retriever, reply templates) can
trust the fields: localities exist in the gazetteer, keywords are in the
vocabulary, prices are positive and ordered.
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass
from typing import Any, Literal

from ai.nlu.gazetteer import resolve_place
from ai.nlu.keyword_vocab import KEYWORD_VOCAB, canonical_keyword
from ai.rag.prompt_templates import _format_price

logger = logging.getLogger(__name__)

PriceUnit = Literal["lakh", "crore", "rupee"]
PropertyType = Literal["flat", "house_land"]
Source = Literal["model", "rules", "hybrid"]

_UNIT_MULTIPLIER: dict[str, int] = {"lakh": 1_00_000, "crore": 1_00_00_000, "rupee": 1}
# Upper sanity bound for any parsed price (Rs.1,000 crore). Anything above is a
# typo or garbage, and would silently disable the budget filter.
MAX_PRICE_RUPEES: float = 1_000 * 1_00_00_000
_PROPERTY_TYPES = ("flat", "house_land")
_BHK_MIN, _BHK_MAX = 1, 10

# The exact, ordered keys the model is trained to emit.
MODEL_OUTPUT_KEYS: tuple[str, ...] = (
    "is_property_query",
    "bhk",
    "locality",
    "price_min",
    "price_max",
    "property_type",
    "keywords",
)


@dataclass(frozen=True)
class RawPrice:
    """A price as written by the user: amount plus unit, not yet converted."""

    amount: float
    unit: PriceUnit


def to_rupees(price: RawPrice | dict[str, Any]) -> float:
    """Convert a RawPrice (or its dict form) to rupees.

    Raises:
        ValueError: If the unit is unknown.
    """
    if isinstance(price, dict):
        amount, unit = price["amount"], price["unit"]
    else:
        amount, unit = price.amount, price.unit
    if unit not in _UNIT_MULTIPLIER:
        raise ValueError(f"unknown price unit {unit!r}")
    return float(amount) * _UNIT_MULTIPLIER[unit]


def is_sane_price(price: RawPrice) -> bool:
    """True if *price* is finite, positive and at most MAX_PRICE_RUPEES.

    JSON allows NaN/Infinity, and PostgreSQL sorts NaN above every number, so
    an unchecked "price_max": NaN would match every listing.
    """
    if not math.isfinite(price.amount) or price.amount <= 0:
        return False
    return to_rupees(price) <= MAX_PRICE_RUPEES


@dataclass(frozen=True)
class ParsedQuery:
    """Structured search filters extracted from one customer message.

    Attributes:
        is_property_query: False for greetings, off-topic questions and
            instruction-override attempts; every other field is then empty.
        bhk: Bedroom count (1-10) when explicitly stated.
        locality: Canonical gazetteer locality or landmark name.
        price_min: Lower budget bound in rupees.
        price_max: Upper budget bound in rupees.
        property_type: "flat" or "house_land".
        keywords: Canonical soft preferences from KEYWORD_VOCAB, in the order
            mentioned.
        source: Which parser produced this: "model", "rules" or "hybrid".
    """

    is_property_query: bool
    bhk: int | None = None
    locality: str | None = None
    price_min: float | None = None
    price_max: float | None = None
    property_type: PropertyType | None = None
    keywords: tuple[str, ...] = ()
    source: Source = "rules"

    def is_empty(self) -> bool:
        """True when no filter at all is set."""
        return (
            self.bhk is None
            and self.locality is None
            and self.price_min is None
            and self.price_max is None
            and self.property_type is None
            and not self.keywords
        )

    def describe(self) -> str:
        """Short human-readable summary, e.g. "3 BHK flat in Vesu, up to Rs.80.0 L"."""
        if not self.is_property_query:
            return "not a property query"

        noun = {"flat": "flat", "house_land": "house or plot", None: "property"}[self.property_type]
        head = f"{self.bhk} BHK {noun}" if self.bhk is not None else noun
        if self.locality is not None:
            head += f" in {self.locality}"

        parts = [head]
        if self.price_min is not None and self.price_max is not None:
            parts.append(f"{_format_price(self.price_min)} to {_format_price(self.price_max)}")
        elif self.price_max is not None:
            parts.append(f"up to {_format_price(self.price_max)}")
        elif self.price_min is not None:
            parts.append(f"from {_format_price(self.price_min)}")
        if self.keywords:
            parts.append("with " + ", ".join(self.keywords))
        return ", ".join(parts)


def _is_int(value: Any) -> bool:
    # bool is a subclass of int; true/false is never a valid bhk.
    return isinstance(value, int) and not isinstance(value, bool)


def _parse_raw_price(value: Any) -> RawPrice | None | Literal[False]:
    """RawPrice for a valid price, None for null, False for a malformed value."""
    if value is None:
        return None
    if not isinstance(value, dict):
        return False
    amount, unit = value.get("amount"), value.get("unit")
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        return False
    if unit not in _UNIT_MULTIPLIER:
        return False
    price = RawPrice(amount=float(amount), unit=unit)
    return price if is_sane_price(price) else False


def validate_model_output(obj: Any) -> ParsedQuery | None:
    """Turn raw model JSON into a trusted ParsedQuery. Never raises.

    Returns None (so the caller falls back to rules) when the object is
    structurally broken: not a dict, ``is_property_query`` missing or not a
    bool, or any present field has the wrong JSON type (e.g. bhk "three",
    keywords "gym"). Missing optional keys count as null — the hand-written
    evaluation set may omit them.

    Semantically wrong values are dropped field by field instead:
      - bhk outside 1-10 -> None
      - locality that doesn't resolve via the gazetteer -> None
      - property_type other than "flat"/"house_land" -> None
      - non-positive, non-finite or absurd (> Rs.1,000 crore) price, unknown
        unit, or price_min > price_max -> both prices dropped
      - keywords mapped through synonyms and filtered to KEYWORD_VOCAB,
        deduplicated in order
    If is_property_query is False every other field is forced empty.
    Unknown extra keys are ignored.
    """
    try:
        return _validate(obj)
    except Exception:  # defensive: validation must never take down a request
        logger.exception("validate_model_output() failed unexpectedly")
        return None


def _validate(obj: Any) -> ParsedQuery | None:
    if not isinstance(obj, dict):
        return None
    is_prop = obj.get("is_property_query")
    if not isinstance(is_prop, bool):
        return None

    bhk = obj.get("bhk")
    locality = obj.get("locality")
    ptype = obj.get("property_type")
    keywords = obj.get("keywords")
    if keywords is None:
        keywords = []

    if bhk is not None and not (_is_int(bhk) or (isinstance(bhk, float) and bhk.is_integer())):
        return None
    if locality is not None and not isinstance(locality, str):
        return None
    if ptype is not None and not isinstance(ptype, str):
        return None
    if not isinstance(keywords, list) or not all(isinstance(k, str) for k in keywords):
        return None
    raw_min = _parse_raw_price(obj.get("price_min"))
    raw_max = _parse_raw_price(obj.get("price_max"))

    if not is_prop:
        return ParsedQuery(is_property_query=False, source="model")

    bhk_val = int(bhk) if bhk is not None and _BHK_MIN <= bhk <= _BHK_MAX else None

    locality_val = None
    if locality and locality.strip():
        resolved = resolve_place(locality)
        locality_val = resolved[0] if resolved else None

    ptype_val = ptype if ptype in _PROPERTY_TYPES else None

    price_min = to_rupees(raw_min) if raw_min else None
    price_max = to_rupees(raw_max) if raw_max else None
    if raw_min is False or raw_max is False or (
        price_min is not None and price_max is not None and price_min > price_max
    ):
        price_min = price_max = None

    kw_out: list[str] = []
    for k in keywords:
        canon = canonical_keyword(k)
        if canon in KEYWORD_VOCAB and canon not in kw_out:
            kw_out.append(canon)

    return ParsedQuery(
        is_property_query=True,
        bhk=bhk_val,
        locality=locality_val,
        price_min=price_min,
        price_max=price_max,
        property_type=ptype_val,
        keywords=tuple(kw_out),
        source="model",
    )


def extract_first_json(text: str) -> dict[str, Any] | None:
    """Parse the first balanced ``{...}`` object in *text*, or return None.

    Models sometimes wrap JSON in prose or code fences; this skips anything
    before the first ``{`` and stops at its matching ``}``, respecting braces
    inside JSON strings. Truncated or invalid JSON returns None.
    """
    if not text:
        return None
    start = text.find("{")
    while start != -1:
        depth = 0
        in_string = False
        escaped = False
        for i in range(start, len(text)):
            ch = text[i]
            if in_string:
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    in_string = False
                continue
            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        parsed = json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        break
                    return parsed if isinstance(parsed, dict) else None
        else:
            return None  # ran out of text: truncated
        start = text.find("{", start + 1)
    return None


def dump_model_output(target: dict[str, Any]) -> str:
    """Serialize a model target as compact JSON with keys in MODEL_OUTPUT_KEYS order.

    Used by the dataset generator so every training label has the same shape.
    Integral amounts are written as ints ("80", not "80.0") to match how
    people type them.
    """
    def clean(value: Any) -> Any:
        if isinstance(value, float) and value.is_integer():
            return int(value)
        if isinstance(value, dict):
            return {k: clean(v) for k, v in value.items()}
        if isinstance(value, list):
            return [clean(v) for v in value]
        return value

    ordered = {key: clean(target.get(key)) for key in MODEL_OUTPUT_KEYS}
    if ordered["keywords"] is None:
        ordered["keywords"] = []
    return json.dumps(ordered, ensure_ascii=False, separators=(",", ":"))
