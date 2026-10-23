"""Chat reply text, built from templates around the retrieved listings.

No language model writes the reply — the fine-tuned model only parses the
query (ai/nlu/query_parser.py). Every property, price and amenity in the
reply comes straight from the ``listings`` passed in, so the reply can't
describe a property that retrieval didn't return. That is the main design
change from the Mistral-7B version (see ai/docs/ADR-002-qwen3-nlu-model.md).
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from ai.nlu.query_parser import parse_query
from ai.nlu.schema import ParsedQuery
from ai.rag.prompt_templates import _build_amenities_summary, _format_price, is_amenity_related

logger = logging.getLogger(__name__)

MAX_LISTED = 5

_FALLBACK_REPLY = (
    "I'm having trouble responding right now — could you try rephrasing your question?"
)

_REDIRECTS = (
    "I can only help with finding properties in Surat. Tell me what you're looking for — "
    "for example, \"2 BHK flat in Adajan under 60 lakh\".",
    "That's outside what I can help with, but I'd be happy to help you find a home. "
    "Which area, budget or BHK do you have in mind?",
    "I'm a property search assistant, so I can't help with that. Try something like "
    "\"plots in Pal above 1 crore\" or \"3 BHK near VR Mall\".",
)

_TYPE_LABELS = {"flat": "flat", "house_land": "house/plot"}


def _pick_redirect(query: str) -> str:
    # hashlib, not hash(): Python's hash() is salted per process, and the same
    # message should get the same reply after a restart.
    digest = hashlib.sha256(query.strip().lower().encode("utf-8")).digest()
    return _REDIRECTS[digest[0] % len(_REDIRECTS)]


def _no_results_reply(parsed: ParsedQuery) -> str:
    if parsed.is_empty():
        return ("I couldn't find any matching properties. Try telling me a locality, "
                "a budget or the number of bedrooms.")
    reply = f"I couldn't find any properties matching {parsed.describe()}."
    if parsed.price_min is not None or parsed.price_max is not None:
        reply += " Nothing came up within that budget — you could try "
        reply += "raising it a little." if parsed.price_max is not None else "lowering the minimum a little."
    elif parsed.bhk is not None:
        reply += f" You could try without the {parsed.bhk} BHK requirement."
    elif parsed.locality is not None:
        reply += " You could try a nearby locality."
    else:
        reply += " You could try describing it a little differently."
    return reply


def _relaxation_sentence(note: str, parsed: ParsedQuery) -> str | None:
    place = parsed.locality
    if note == "relaxed_radius" and place:
        return f"I couldn't find exact matches in {place}, so I included nearby areas."
    if note == "relaxed_bhk":
        where = f" in or near {place}" if place else ""
        return f"I couldn't find a {parsed.bhk} BHK{where}, so I've included other sizes."
    if note == "relaxed_locality" and place:
        return f"Nothing matched in or near {place}, so these are from other parts of Surat."
    return None


def _amenities_of(listing: dict[str, Any]) -> dict | None:
    amenities = listing.get("amenities")
    if isinstance(amenities, str):
        try:
            amenities = json.loads(amenities)
        except (json.JSONDecodeError, TypeError):
            return None
    return amenities if isinstance(amenities, dict) else None


def _listing_line(i: int, listing: dict[str, Any]) -> str:
    parts = [_format_price(listing.get("price"))]
    ptype = _TYPE_LABELS.get(listing.get("property_type"))
    if ptype:
        parts.append(ptype)
    if listing.get("bhk"):
        parts.append(f"{listing['bhk']} BHK")
    return f"{i}. {listing.get('title') or 'Untitled listing'} — {', '.join(parts)}"


def _build_reply(query: str, listings: list[dict[str, Any]]) -> str:
    parsed = parse_query(query)
    if not parsed.is_property_query:
        return _pick_redirect(query)
    if not listings:
        return _no_results_reply(parsed)

    shown = listings[:MAX_LISTED]
    notes = [l.get("match_note") or "exact" for l in shown]
    relaxed = any(n != "exact" for n in notes)
    count = f"{len(shown)} propert{'y' if len(shown) == 1 else 'ies'}"
    if parsed.is_empty():
        lines = [f"Here {'is' if len(shown) == 1 else 'are'} {count} you might like:"]
    elif relaxed:
        lines = [f"Here {'is' if len(shown) == 1 else 'are'} {count} close to what you asked for "
                 f"({parsed.describe()}):"]
    else:
        lines = [f"Here {'is' if len(shown) == 1 else 'are'} {count} matching {parsed.describe()}:"]

    seen_notes: list[str] = []
    for note in notes:
        sentence = _relaxation_sentence(note, parsed)
        if sentence and sentence not in seen_notes:
            seen_notes.append(sentence)
    lines += seen_notes

    show_amenities = is_amenity_related(query)
    for i, listing in enumerate(shown, 1):
        lines.append(_listing_line(i, listing))
        if show_amenities:
            summary = _build_amenities_summary(_amenities_of(listing))
            lines.append(f"   {summary}" if summary
                         else "   Nearby-amenities information isn't available for this listing yet.")
    return "\n".join(lines)


def generate_response(query: str, listings: list[dict], history: list[dict] | None) -> str:
    """Build the assistant's reply to a customer message.

    Signature matches AGENTS.md exactly — Person 2's /chat route calls this
    directly. Deterministic: the same query and listings always give the same
    reply. Never calls a language model and never raises.

    Args:
        query: The customer's current message.
        listings: Results of ai.rag.retriever.search() for this message (each
            may carry a "match_note" saying how the search was relaxed).
        history: Prior conversation turns, oldest first, or None. Not used yet
            (follow-up questions are optional Part F of the playbook).

    Returns:
        The reply text. On any internal failure, a short apologetic fallback.
    """
    try:
        return _build_reply(query or "", listings or [])
    except Exception:
        logger.exception("generate_response() failed for query=%r", (query or "")[:60])
        return _FALLBACK_REPLY
