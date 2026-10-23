"""Deterministic rules parser — the baseline and the fallback for query understanding.

``parse_with_rules`` implements ``ai/nlu/LABELING_RULES.md`` with regular
expressions plus the gazetteer. It needs no GPU and no model, so it is what
runs when the fine-tuned model is unavailable, and it is the baseline the
model has to beat on the hand-written evaluation set.

Price extraction lives here (``extract_prices``) and is the one place in the
codebase that turns "80 lakh" / "1.2cr" / "Rs 80,00,000" into amounts: the
hybrid parser always prefers these prices over the model's, because regex
arithmetic is exact and tested.
"""

from __future__ import annotations

import re

from ai.nlu.gazetteer import resolve_place
from ai.nlu.keyword_vocab import KEYWORD_SYNONYMS, KEYWORD_VOCAB
from ai.nlu.schema import ParsedQuery, RawPrice, to_rupees

# ---------------------------------------------------------------------------
# Prices
# ---------------------------------------------------------------------------

_NUM = r"(\d+(?:,\d+)*(?:\.\d+)?)"
# Spaced units ("80 lakh", "2 cr") or a bare "l" glued to the number ("80L").
# A spaced "80 l" is not accepted — too easy to collide with other text.
_UNIT = r"(?:\s*(crores?|crs?|lakhs?|lacs?|lkh)|(l))(?![a-z])"
_UNIT_NAMES = {
    "crore": "crore", "crores": "crore", "cr": "crore", "crs": "crore",
    "lakh": "lakh", "lakhs": "lakh", "lac": "lakh", "lacs": "lakh", "lkh": "lakh", "l": "lakh",
}
_RS = r"(?:(?:rs\.?|inr)\s*)?"
_NOT_AREA = r"(?!\s*(?:sq|square|ft|feet|sqft|sq\.?\s*ft|yards?|gaj|vigha|bigha))"

_RANGE_RE = re.compile(
    rf"{_RS}{_NUM}(?:{_UNIT})?\s*(?:-|–|to|and|se|thi)\s*{_RS}{_NUM}{_UNIT}"
)
_UNIT_PRICE_RE = re.compile(rf"(?<![\d.]){_NUM}{_UNIT}")
_RUPEE_PRICE_RE = re.compile(rf"(?:rs\.?|inr)\s*{_NUM}{_NOT_AREA}(?![\d,])")
_BARE_BIG_RE = re.compile(rf"(?<![\d.,]){_NUM}{_NOT_AREA}(?![\d,.])")

_FILLER = r"(?:\s+(?:of|a|an|the|rs\.?|inr|budget|price|is|my|our|around|about))*"
_MAX_BEFORE = re.compile(
    r"(?:under|below|upto|up\s+to|max|maximum|within|less\s+than|not\s+more\s+than|"
    r"no\s+more\s+than|at\s+most|budget|cheaper\s+than|lower\s+than|till|until|<)"
    + _FILLER + r"\s*$"
)
_MIN_BEFORE = re.compile(
    r"(?:above|over|at\s*least|min|minimum|more\s+than|greater\s+than|not\s+less\s+than|"
    r"starting|starting\s+from|starting\s+at|from|upwards\s+of|>)"
    + _FILLER + r"\s*$"
)
_MAX_AFTER = re.compile(
    r"^\s*(?:tak|sudhi|sudhee|se\s+kam|thi\s+ochhu|thi\s+ochu|thi\s+ocha|or\s+less|or\s+below|"
    r"and\s+below|or\s+under|max|maximum)\b"
)
_MIN_AFTER = re.compile(
    r"^\s*(?:\+|(?:plus|and\s+above|or\s+above|or\s+more|onwards|upwards|se\s+upar|se\s+uper|"
    r"se\s+zyada|se\s+jyada|se\s+adhik|thi\s+vadhare|thi\s+vadhu|thi\s+upar|minimum)\b)"
)

# Any rupee figure at or above this, written without a unit, is a price.
_BARE_PRICE_MIN_RUPEES = 1_00_000


def _amount(num: str) -> float:
    return float(num.replace(",", ""))


def _unit_of(spaced: str | None, glued: str | None) -> str | None:
    unit = spaced or glued
    return _UNIT_NAMES[unit] if unit else None


def _range_prices(text: str, mask: list[bool]) -> tuple[RawPrice, RawPrice] | None:
    for m in _RANGE_RE.finditer(text):
        if any(mask[m.start():m.end()]):
            continue
        a_num, a_sp, a_gl, b_num, b_sp, b_gl = m.groups()
        b_unit = _unit_of(b_sp, b_gl)
        a_unit = _unit_of(a_sp, a_gl) or b_unit
        low, high = RawPrice(_amount(a_num), a_unit), RawPrice(_amount(b_num), b_unit)
        if _unit_of(a_sp, a_gl) is None and to_rupees(low) > to_rupees(high) and b_unit == "crore":
            # "between 80 and 1.2 crore" means 80 lakh, not 80 crore.
            low = RawPrice(low.amount, "lakh")
        if to_rupees(low) > to_rupees(high):
            low, high = high, low
        for i in range(m.start(), m.end()):
            mask[i] = True
        return low, high
    return None


def _single_prices(text: str, mask: list[bool]) -> list[tuple[int, int, RawPrice]]:
    found: list[tuple[int, int, RawPrice]] = []

    def take(start: int, end: int, price: RawPrice) -> None:
        if any(mask[start:end]):
            return
        for i in range(start, end):
            mask[i] = True
        found.append((start, end, price))

    for m in _UNIT_PRICE_RE.finditer(text):
        take(m.start(), m.end(), RawPrice(_amount(m.group(1)), _unit_of(m.group(2), m.group(3))))
    for m in _RUPEE_PRICE_RE.finditer(text):
        take(m.start(), m.end(), RawPrice(_amount(m.group(1)), "rupee"))
    for m in _BARE_BIG_RE.finditer(text):
        amount = _amount(m.group(1))
        if amount >= _BARE_PRICE_MIN_RUPEES:
            take(m.start(), m.end(), RawPrice(amount, "rupee"))
    found.sort(key=lambda item: item[0])
    return found


def extract_prices(query: str) -> tuple[RawPrice | None, RawPrice | None]:
    """Extract (price_min, price_max) as written, following LABELING_RULES.md.

    Handles lakh/crore/rupee formats ("80L", "80 lakh", "80 lacs", "Rs 80 lakh",
    "0.8 cr", "1.2cr", "Rs 80,00,000"), direction words before the number
    ("under", "above", "budget of", ...), Hinglish/Gujarati postpositions after
    it ("tak", "se upar", "sudhi", "thi vadhare", ...), and ranges ("between X
    and Y", "X to Y", "X-Y lakh", "X se Y", "X thi Y"). A price with no
    direction is the budget, i.e. price_max. An inverted min/max pair is
    dropped entirely.

    Returns:
        (price_min, price_max); either may be None.
    """
    text = " ".join(query.lower().replace("₹", " rs ").split())
    mask = [False] * len(text)

    price_min: RawPrice | None = None
    price_max: RawPrice | None = None

    rng = _range_prices(text, mask)
    if rng is not None:
        price_min, price_max = rng

    prev_end = 0
    for start, end, price in _single_prices(text, mask):
        before = text[prev_end:start]
        after = text[end:end + 25]
        prev_end = end
        if _MIN_BEFORE.search(before) or (not _MAX_BEFORE.search(before) and _MIN_AFTER.search(after)):
            if price_min is None:
                price_min = price
        elif _MAX_BEFORE.search(before) or _MAX_AFTER.search(after):
            if price_max is None:
                price_max = price
        elif price_max is None:
            price_max = price  # bare price = budget

    if price_min and price_max and to_rupees(price_min) > to_rupees(price_max):
        return None, None
    return price_min, price_max


# ---------------------------------------------------------------------------
# BHK
# ---------------------------------------------------------------------------

_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    # Hinglish
    "ek": 1, "do": 2, "teen": 3, "char": 4, "chaar": 4, "paanch": 5, "panch": 5,
    # Gujarati-in-English
    "be": 2, "tran": 3, "tranh": 3,
}
_BHK_SUFFIX = r"\s*-?\s*(?:bhk|b\.h\.k\.?|(?:bedrooms?|beds?|br)(?![a-z]))"
_BHK_PATTERNS = [
    # "2 or 3 bhk" -> the first count
    (re.compile(r"(?<![\d.])(\d{1,2})\s*(?:or|/|-|to)\s*\d{1,2}" + _BHK_SUFFIX), None),
    (re.compile(r"(?<![\d.])(\d{1,2})" + _BHK_SUFFIX), None),
    (re.compile(r"\b(" + "|".join(_NUMBER_WORDS) + r")" + _BHK_SUFFIX), "word"),
    (re.compile(r"\bstudio\b|(?<![\d.])1\s*-?\s*rk\b"), "one"),
]


def extract_bhk(query: str) -> int | None:
    """Bedroom count from explicit mentions only; the earliest mention wins."""
    text = query.lower()
    best: tuple[int, int] | None = None
    for pattern, kind in _BHK_PATTERNS:
        m = pattern.search(text)
        if not m:
            continue
        if kind == "one":
            value = 1
        elif kind == "word":
            value = _NUMBER_WORDS[m.group(1)]
        else:
            value = int(m.group(1))
        if best is None or m.start() < best[0]:
            best = (m.start(), value)
    if best is None or not 1 <= best[1] <= 10:
        return None
    return best[1]


# ---------------------------------------------------------------------------
# Keywords, property type, locality
# ---------------------------------------------------------------------------

_KEYWORD_PHRASES = sorted(
    {**{k: k for k in KEYWORD_VOCAB}, **KEYWORD_SYNONYMS}.items(),
    key=lambda item: len(item[0]),
    reverse=True,
)
_KEYWORD_RES = [
    (re.compile(r"(?<![a-z])" + r"[\s-]+".join(map(re.escape, phrase.split())) + r"(?![a-z])"), canon)
    for phrase, canon in _KEYWORD_PHRASES
]
_NEGATED = re.compile(r"(?:\bno|\bnon|\bnot|\bwithout)[\s-]*$")


def extract_keywords(query: str) -> tuple[str, ...]:
    """Canonical keywords in mention order, deduplicated.

    Longer phrases are matched first and blanked out, so "semi furnished" is
    not also counted as "furnished". Negated mentions ("without parking",
    "non-furnished") are skipped.
    """
    text = query.lower()
    hits: list[tuple[int, str]] = []
    for pattern, canon in _KEYWORD_RES:
        for m in pattern.finditer(text):
            if _NEGATED.search(text[:m.start()]):
                continue
            hits.append((m.start(), canon))
            text = text[:m.start()] + " " * (m.end() - m.start()) + text[m.end():]
    ordered: list[str] = []
    for _, canon in sorted(hits):
        if canon not in ordered:
            ordered.append(canon)
    return tuple(ordered)


_FLAT_RE = re.compile(r"\b(?:flats?|apartments?|apts?|penthouses?)\b")
_HOUSE_LAND_RE = re.compile(
    r"\b(?:plots?|lands?|villas?|bungalows?|row[\s-]?houses?|houses?|tenements?|makaa?n)\b"
)


_CLUBHOUSE_RE = re.compile(r"club[\s-]*house")


def extract_property_type(query: str) -> str | None:
    """"flat" or "house_land" from type words; the first mentioned wins.

    "club house" is an amenity, so it is removed before looking for "house".
    """
    text = _CLUBHOUSE_RE.sub(" ", query.lower())
    flat, house = _FLAT_RE.search(text), _HOUSE_LAND_RE.search(text)
    if flat and house:
        return "flat" if flat.start() < house.start() else "house_land"
    if flat:
        return "flat"
    if house:
        return "house_land"
    return None


def extract_locality(query: str) -> str | None:
    """Canonical place name: exact whole-word match first, then fuzzy n-grams.

    Fuzzy matching runs on 3-, then 2-, then 1-word windows (skipping windows
    with digits), so a misspelled "ghod dod raod" or "piploud" inside a longer
    sentence still resolves.
    """
    # "3bhkvesu" -> "3bhk vesu": a dropped space after bhk is a common typo.
    text = re.sub(r"bhk(?=[a-z])", "bhk ", query.lower())
    exact = resolve_place(text)
    if exact:
        return exact[0]
    words = re.findall(r"[a-z][a-z.\-]*", text)
    for size in (3, 2, 1):
        for i in range(len(words) - size + 1):
            hit = resolve_place(" ".join(words[i:i + size]))
            if hit:
                return hit[0]
    return None


# ---------------------------------------------------------------------------
# Property-query detection
# ---------------------------------------------------------------------------

_OVERRIDE_RE = re.compile(
    r"\b(?:ignore|disregard|forget)\b.{0,40}\b(?:instructions?|rules|prompt|guidelines)\b"
    r"|\bsystem\s+prompt\b|\byou\s+are\s+now\b|\bpretend\s+(?:to\s+be|you\s+are)\b"
    r"|\bjailbreak\b|\bdeveloper\s+mode\b"
)
_PROPERTY_WORDS_RE = re.compile(
    r"\b(?:flats?|houses?|property|properties|rent|rental|buy|buying|purchase|homes?|"
    r"apartments?|plots?|bhk|villas?|bungalows?|land|real\s+estate|listings?|ghar|makaan|"
    r"makan|resale|tenements?|penthouses?)\b"
)


def parse_with_rules(query: str) -> ParsedQuery:
    """Parse *query* into a ParsedQuery using only deterministic rules.

    Never raises. Empty or whitespace-only input, and instruction-override
    attempts, are not property queries.
    """
    if not isinstance(query, str) or not query.strip():
        return ParsedQuery(is_property_query=False, source="rules")
    text = " ".join(query.split())
    lowered = text.lower()

    if _OVERRIDE_RE.search(lowered):
        return ParsedQuery(is_property_query=False, source="rules")

    raw_min, raw_max = extract_prices(text)
    bhk = extract_bhk(text)
    keywords = extract_keywords(text)
    property_type = extract_property_type(text)
    locality = extract_locality(text)

    has_signal = any(
        v is not None for v in (raw_min, raw_max, bhk, property_type, locality)
    ) or bool(keywords) or bool(_PROPERTY_WORDS_RE.search(_CLUBHOUSE_RE.sub(" ", lowered)))
    if not has_signal:
        return ParsedQuery(is_property_query=False, source="rules")

    return ParsedQuery(
        is_property_query=True,
        bhk=bhk,
        locality=locality,
        price_min=to_rupees(raw_min) if raw_min else None,
        price_max=to_rupees(raw_max) if raw_max else None,
        property_type=property_type,
        keywords=keywords,
        source="rules",
    )
