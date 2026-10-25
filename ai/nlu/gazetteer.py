"""Surat place gazetteer — localities and landmarks a customer might type.

Every place the NLU layer can put into ``ParsedQuery.locality`` comes from
this file. The retriever turns the canonical name back into a centroid and a
radius and filters listings with PostGIS ``ST_DWithin`` — so a name that
isn't in here can never become a location filter, which is what stops the
model from inventing a locality.

Locality centroids are copied verbatim from ``NEIGHBOURHOODS`` in
``ai/embeddings/_test_seed.py`` (the test ``test_gazetteer.py`` checks they
stay in sync). They are not imported from there because that script exits
the process when ``DATABASE_URL`` is unset.
"""

from __future__ import annotations

import re
from typing import Any

from rapidfuzz import fuzz

# ---------------------------------------------------------------------------
# Localities
# ---------------------------------------------------------------------------
# radius_m: how far from the centroid still counts as "in" the locality.
#   1500 — dense central areas (Athwa, Ghod Dod Road, Citylight, Udhna,
#          Varachha, Katargam, Althan, Piplod): neighbourhoods are small and
#          a 2km circle would swallow the next locality over.
#   2000 — the default for established residential areas.
#   2500 — outlying areas (Dumas, Sachin, Sarthana, Jahangirpura, Puna
#          Kumbharia, Pal, Palanpur, Rander): spread out, fewer listings, a
#          tighter circle would often return nothing.
# Note: _test_seed.py jitters listings up to ~1.3km from the centroid, so a
# few seeded listings in 1500m localities sit just outside the circle; the
# retriever's relaxation ladder (radius x2) picks them up.
LOCALITIES: dict[str, dict[str, Any]] = {
    "Adajan": {
        "lat": 21.1848, "lng": 72.7803, "radius_m": 2000,
        "aliases": ["adajan", "adajan gam", "adajan gaam", "adajan area"],
    },
    "Vesu": {
        "lat": 21.1545, "lng": 72.7757, "radius_m": 2000,
        "aliases": ["vesu", "vessu", "vesu area"],
    },
    "Athwa": {
        "lat": 21.1880, "lng": 72.8263, "radius_m": 1500,
        "aliases": ["athwa", "athwalines", "athwa lines", "athva"],
    },
    "Piplod": {
        "lat": 21.1600, "lng": 72.8000, "radius_m": 1500,
        "aliases": ["piplod", "pipload"],
    },
    "Citylight": {
        "lat": 21.1724, "lng": 72.8101, "radius_m": 1500,
        "aliases": ["citylight", "city light", "city-light", "citilight"],
    },
    "Pal": {
        "lat": 21.1977, "lng": 72.7742, "radius_m": 2500,
        "aliases": ["pal", "pal gam", "pal gaam", "pal area"],
    },
    "Althan": {
        "lat": 21.1674, "lng": 72.8180, "radius_m": 1500,
        "aliases": ["althan", "althaan"],
    },
    "Bhatar": {
        "lat": 21.1670, "lng": 72.8138, "radius_m": 2000,
        "aliases": ["bhatar", "bhataar"],
    },
    "Ghod Dod Road": {
        "lat": 21.1790, "lng": 72.8198, "radius_m": 1500,
        "aliases": [
            "ghod dod road", "ghod dod rd", "ghoddod road", "ghoddod rd",
            "ghod dod", "ghoddod", "ghod-dod road", "ghod-dod",
        ],
    },
    "Palanpur": {
        "lat": 21.2088, "lng": 72.8056, "radius_m": 2500,
        "aliases": ["palanpur", "palanpor", "palanpur gam"],
    },
    "Jahangirpura": {
        "lat": 21.2218, "lng": 72.8289, "radius_m": 2500,
        "aliases": ["jahangirpura", "jahangirpur", "jhangirpura"],
    },
    "Varachha": {
        "lat": 21.2197, "lng": 72.8684, "radius_m": 1500,
        "aliases": ["varachha", "varacha", "varaccha"],
    },
    "Katargam": {
        "lat": 21.2377, "lng": 72.8428, "radius_m": 1500,
        "aliases": ["katargam", "katargaam"],
    },
    "Udhna": {
        "lat": 21.1688, "lng": 72.8447, "radius_m": 1500,
        "aliases": ["udhna", "udhana"],
    },
    "Dumas": {
        "lat": 21.0977, "lng": 72.7166, "radius_m": 2500,
        "aliases": ["dumas", "dumas gam"],
    },
    "Sarthana": {
        "lat": 21.2356, "lng": 72.8741, "radius_m": 2500,
        "aliases": ["sarthana", "sarthana area"],
    },
    "Rander": {
        "lat": 21.2360, "lng": 72.7669, "radius_m": 2500,
        "aliases": ["rander", "rander gam"],
    },
    "Sachin": {
        "lat": 21.0862, "lng": 72.8641, "radius_m": 2500,
        "aliases": ["sachin"],
    },
    "Puna Kumbharia": {
        "lat": 21.1995, "lng": 72.8642, "radius_m": 2500,
        "aliases": [
            "puna kumbharia", "punakumbharia", "puna kumbhariya",
            "kumbharia", "kumbhariya", "puna",
        ],
    },
    "Kapodra": {
        "lat": 21.2212, "lng": 72.8746, "radius_m": 2000,
        "aliases": ["kapodra", "kapodara"],
    },
}

# ---------------------------------------------------------------------------
# Landmarks
# ---------------------------------------------------------------------------
# Places people type instead of a locality. Coordinates are approximate and
# each one is marked "verify on Google Maps" — check them before the demo.
# Deliberately NOT included from _test_seed.py's landmark lists, because a
# point + radius would be misleading for them: "Tapi River", "Arabian Sea",
# "BRTS", "GIDC", "NH-48", "Surat-Navsari Highway", "Surat-Gandhinagar
# Highway" (lines or city-wide networks, not places).
LANDMARKS: dict[str, dict[str, Any]] = {
    "VR Mall": {"lat": 21.1446, "lng": 72.7571, "radius_m": 2000,  # verify on Google Maps
                "aliases": ["vr mall", "v r mall", "vrmall", "vr surat"]},
    "Surat Railway Station": {"lat": 21.2050, "lng": 72.8406, "radius_m": 2000,  # verify on Google Maps
                              "aliases": ["surat railway station", "railway station",
                                          "surat station", "rly station"]},
    "Dumas Beach": {"lat": 21.0790, "lng": 72.7130, "radius_m": 2500,  # verify on Google Maps
                    "aliases": ["dumas beach"]},
    "Dumas Road": {"lat": 21.1430, "lng": 72.7620, "radius_m": 2000,  # verify on Google Maps
                   "aliases": ["dumas road", "dumas rd"]},
    "Parle Point": {"lat": 21.1755, "lng": 72.8040, "radius_m": 1500,  # verify on Google Maps
                    "aliases": ["parle point", "parle pt"]},
    "Ring Road": {"lat": 21.1950, "lng": 72.8380, "radius_m": 2500,  # verify on Google Maps
                  "aliases": ["ring road", "surat ring road", "ring rd"]},
    "Canal Road": {"lat": 21.1640, "lng": 72.7980, "radius_m": 2000,  # verify on Google Maps
                   "aliases": ["canal road", "canal rd"]},
    "VIP Road": {"lat": 21.1520, "lng": 72.7900, "radius_m": 2000,  # verify on Google Maps
                 "aliases": ["vip road", "v.i.p road", "vip rd"]},
    "Surat Municipal Market": {"lat": 21.1994, "lng": 72.8144, "radius_m": 1500,
                               "aliases": ["surat municipal market", "municipal market"]},
    "Sarthana Nature Park": {"lat": 21.2328, "lng": 72.9033, "radius_m": 2000,  # verify on Google Maps
                             "aliases": ["sarthana nature park", "sarthana zoo", "nature park"]},
    "Surat Airport": {"lat": 21.1141, "lng": 72.7418, "radius_m": 2500,  # verify on Google Maps
                      "aliases": ["surat airport", "airport"]},
    "Adajan Patiya": {"lat": 21.1960, "lng": 72.7950, "radius_m": 1500,  # verify on Google Maps
                      "aliases": ["adajan patiya", "adajan patia"]},
    "L.P. Savani School": {"lat": 21.1890, "lng": 72.7880, "radius_m": 1500,  # verify on Google Maps
                           "aliases": ["l.p. savani school", "lp savani school", "lp savani",
                                       "l p savani"]},
    "Vesu Main Road": {"lat": 21.1490, "lng": 72.7790, "radius_m": 1500,  # verify on Google Maps
                       "aliases": ["vesu main road", "vesu main rd"]},
    "Athwa Gate": {"lat": 21.1880, "lng": 72.8170, "radius_m": 1500,  # verify on Google Maps
                   "aliases": ["athwa gate"]},
    "Piplod Circle": {"lat": 21.1610, "lng": 72.7990, "radius_m": 1500,  # verify on Google Maps
                      "aliases": ["piplod circle"]},
    "Udhna Darwaja": {"lat": 21.1830, "lng": 72.8320, "radius_m": 1500,  # verify on Google Maps
                      "aliases": ["udhna darwaja", "udhna darwaza"]},
    "Citylight Road": {"lat": 21.1700, "lng": 72.8060, "radius_m": 1500,  # verify on Google Maps
                       "aliases": ["citylight road", "city light road", "citylight rd"]},
    "Citylight Cinema": {"lat": 21.1730, "lng": 72.8110, "radius_m": 1500,  # verify on Google Maps
                         "aliases": ["citylight cinema", "city light cinema"]},
    "Pal Circle": {"lat": 21.1960, "lng": 72.7750, "radius_m": 1500,  # verify on Google Maps
                   "aliases": ["pal circle"]},
    "Althan Circle": {"lat": 21.1660, "lng": 72.8190, "radius_m": 1500,  # verify on Google Maps
                      "aliases": ["althan circle"]},
    "Bhatar Char Rasta": {"lat": 21.1691, "lng": 72.8139, "radius_m": 1500,
                          "aliases": ["bhatar char rasta", "bhatar char rasto", "bhatar road",
                                      "bhatar rd"]},
    "Ghod Dod Circle": {"lat": 21.1800, "lng": 72.8180, "radius_m": 1500,  # verify on Google Maps
                        "aliases": ["ghod dod circle", "ghoddod circle"]},
    "Palanpur Patia": {"lat": 21.2090, "lng": 72.8000, "radius_m": 1500,  # verify on Google Maps
                       "aliases": ["palanpur patia", "palanpur patiya"]},
    "Varachha Road": {"lat": 21.2120, "lng": 72.8600, "radius_m": 2000,  # verify on Google Maps
                      "aliases": ["varachha road", "varachha rd", "varacha road"]},
    "Diamond Market": {"lat": 21.2110, "lng": 72.8560, "radius_m": 1500,  # verify on Google Maps
                       "aliases": ["diamond market", "mini bazaar", "mini bazar"]},
    "Katargam Gate": {"lat": 21.2190, "lng": 72.8320, "radius_m": 1500,  # verify on Google Maps
                      "aliases": ["katargam gate", "katargam darwaja"]},
    "Textile Market": {"lat": 21.1960, "lng": 72.8420, "radius_m": 1500,  # verify on Google Maps
                       "aliases": ["textile market", "surat textile market"]},
    "Udhna Magdalla Road": {"lat": 21.1700, "lng": 72.8300, "radius_m": 2000,  # verify on Google Maps
                            "aliases": ["udhna magdalla road", "udhna-magdalla road"]},
    "Rander Road": {"lat": 21.2120, "lng": 72.7890, "radius_m": 2000,  # verify on Google Maps
                    "aliases": ["rander road", "rander rd"]},
    "Hazira Road": {"lat": 21.1650, "lng": 72.7350, "radius_m": 2500,  # verify on Google Maps
                    "aliases": ["hazira road", "hazira rd"]},
    "Kapodra Circle": {"lat": 21.2120, "lng": 72.8710, "radius_m": 1500,  # verify on Google Maps
                       "aliases": ["kapodra circle"]},
    "Gaurav Path": {"lat": 21.1625, "lng": 72.7712, "radius_m": 1500,
                    "aliases": ["gaurav path", "gaurav path road"]},
}

# Fuzzy matching is only attempted when the whole input looks like a
# misspelled place name (see resolve_place). 88 keeps "ghod dod raod" and
# "piploud" matching while rejecting ordinary English words.
_FUZZY_MIN_SCORE = 88
_FUZZY_MIN_LENGTH = 4


def _build_index() -> list[tuple[str, str, dict[str, Any]]]:
    """(lowercase surface form, canonical name, info) for every name and alias."""
    index: list[tuple[str, str, dict[str, Any]]] = []
    for kind, table in (("locality", LOCALITIES), ("landmark", LANDMARKS)):
        for canonical, data in table.items():
            info = {"lat": data["lat"], "lng": data["lng"],
                    "radius_m": data["radius_m"], "kind": kind}
            surfaces = {canonical.lower(), *(a.lower() for a in data["aliases"])}
            for surface in surfaces:
                index.append((surface, canonical, info))
    # Longest surface first, so "dumas road" wins over "dumas".
    index.sort(key=lambda item: len(item[0]), reverse=True)
    return index


_INDEX = _build_index()
_PATTERNS = [
    (re.compile(r"(?<![a-z0-9])" + re.escape(surface) + r"(?![a-z0-9])"), canonical, info)
    for surface, canonical, info in _INDEX
]


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def resolve_place(text: str) -> tuple[str, dict[str, Any]] | None:
    """Find the Surat locality or landmark mentioned in *text*.

    Exact matching scans the whole text for any canonical name or alias as a
    whole word (case-insensitive). When several places match, overlapping
    matches keep the longest one ("Dumas Road" beats "Dumas"), and among the
    rest the one mentioned first wins — the labeling rules use the first
    locality when a query names two.

    If nothing matches exactly, the whole text is fuzzy-compared against every
    name (rapidfuzz ratio >= 88) to catch misspellings. Callers that want to
    fuzzy-match a phrase inside a longer query should pass n-grams, as
    ``ai.nlu.rules`` does. Inputs shorter than 4 characters are never
    fuzzy-matched.

    Args:
        text: A query or a fragment of one.

    Returns:
        ``(canonical_name, info)`` where info has ``lat``, ``lng``,
        ``radius_m`` and ``kind`` ("locality" or "landmark"), or None.
    """
    if not text:
        return None
    normalized = _normalize(text)
    if not normalized:
        return None

    taken: list[tuple[int, int]] = []
    found: list[tuple[int, str, dict[str, Any]]] = []
    for pattern, canonical, info in _PATTERNS:
        for match in pattern.finditer(normalized):
            start, end = match.span()
            if any(start < t_end and end > t_start for t_start, t_end in taken):
                continue  # inside a longer match already found
            taken.append((start, end))
            found.append((start, canonical, info))
    if found:
        _, canonical, info = min(found, key=lambda item: item[0])
        return canonical, dict(info)

    if len(normalized) < _FUZZY_MIN_LENGTH:
        return None
    best: tuple[float, str, dict[str, Any]] | None = None
    for surface, canonical, info in _INDEX:
        if len(surface) < _FUZZY_MIN_LENGTH:
            continue
        score = fuzz.ratio(normalized, surface)
        if score >= _FUZZY_MIN_SCORE and (best is None or score > best[0]):
            best = (score, canonical, info)
    if best is None:
        return None
    return best[1], dict(best[2])


def surface_forms(canonical: str) -> set[str]:
    """Lowercase canonical name plus aliases of a place; empty set if unknown."""
    data = LOCALITIES.get(canonical) or LANDMARKS.get(canonical)
    if data is None:
        return set()
    return {canonical.lower(), *(a.lower() for a in data["aliases"])}


def get_place(canonical: str) -> dict[str, Any] | None:
    """Look up a canonical locality or landmark name (exact, case-sensitive)."""
    data = LOCALITIES.get(canonical) or LANDMARKS.get(canonical)
    if data is None:
        return None
    kind = "locality" if canonical in LOCALITIES else "landmark"
    return {"lat": data["lat"], "lng": data["lng"], "radius_m": data["radius_m"], "kind": kind}
