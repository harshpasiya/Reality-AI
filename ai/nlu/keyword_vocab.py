"""Soft-preference keywords the NLU layer may emit.

``ParsedQuery.keywords`` only ever contains items from ``KEYWORD_VOCAB``.
Keywords don't filter in SQL — they ride along in the original query text
that gets embedded, and are surfaced in the reply summary. Keeping them to a
fixed list means the model can't invent a preference.

Words like "cheap", "luxury" or "sasta" are deliberately absent: they are not
features of a listing, and they must never turn into a price either.
"""

from __future__ import annotations

KEYWORD_VOCAB: list[str] = [
    "gym",
    "swimming pool",
    "parking",
    "garden",
    "balcony",
    "furnished",
    "semi-furnished",
    "gated society",
    "clubhouse",
    "lift",
    "corner plot",
    "east facing",
    "north facing",
    "near park",
    "near school",
    "near hospital",
    "near metro",
    "near mall",
    "spacious",
    "new construction",
    "ready to move",
]

# Common phrasing -> canonical keyword. All lowercase. Matching code tries
# longer phrases first, so "semi furnished" is consumed before "furnished".
KEYWORD_SYNONYMS: dict[str, str] = {
    # amenities inside the society
    "gymnasium": "gym",
    "fitness centre": "gym",
    "fitness center": "gym",
    "pool": "swimming pool",
    "swimming": "swimming pool",
    "car park": "parking",
    "car parking": "parking",
    "covered parking": "parking",
    "parking space": "parking",
    "garden facing": "garden",
    "lawn": "garden",
    "balconies": "balcony",
    "sit out": "balcony",
    "fully furnished": "furnished",
    "full furnished": "furnished",
    "semi furnished": "semi-furnished",
    "semifurnished": "semi-furnished",
    "gated community": "gated society",
    "gated complex": "gated society",
    "club house": "clubhouse",
    "elevator": "lift",
    "corner property": "corner plot",
    "east-facing": "east facing",
    "east face": "east facing",
    "north-facing": "north facing",
    "north face": "north facing",
    # proximity
    "near a park": "near park",
    "near the park": "near park",
    "close to a park": "near park",
    "close to park": "near park",
    "park nearby": "near park",
    "near a school": "near school",
    "near the school": "near school",
    "close to a school": "near school",
    "close to school": "near school",
    "school nearby": "near school",
    "near a hospital": "near hospital",
    "near the hospital": "near hospital",
    "close to a hospital": "near hospital",
    "close to hospital": "near hospital",
    "hospital nearby": "near hospital",
    "near metro station": "near metro",
    "near the metro": "near metro",
    "near a metro station": "near metro",
    "close to metro": "near metro",
    "metro nearby": "near metro",
    "near a mall": "near mall",
    "near the mall": "near mall",
    "close to a mall": "near mall",
    "close to mall": "near mall",
    "mall nearby": "near mall",
    # size / condition
    "big": "spacious",
    "large": "spacious",
    "roomy": "spacious",
    "brand new": "new construction",
    "newly built": "new construction",
    "new project": "new construction",
    "under construction": "new construction",
    "ready-to-move": "ready to move",
    "ready possession": "ready to move",
    "immediate possession": "ready to move",
}


def canonical_keyword(phrase: str) -> str | None:
    """Map a phrase to its canonical keyword, or None if it isn't one."""
    p = " ".join(phrase.lower().split())
    if p in KEYWORD_VOCAB:
        return p
    return KEYWORD_SYNONYMS.get(p)
