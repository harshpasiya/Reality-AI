"""Multi-turn chat: remember the search across messages.

``ai.rag.retriever.search()`` and ``ai.inference.generate_response()`` look at
one message at a time, so "show cheaper ones" or "what about Adajan?" lost
the earlier context.  ``chat_turn()`` keeps it:

* **Carry-over.** Filters from the previous search are kept unless the new
  message changes them: after "2 BHK in Vesu under 80 lakh", "what about
  Adajan?" searches 2 BHK in Adajan under 80 lakh.
* **Relative follow-ups.** "cheaper" lowers the budget, "more expensive"
  raises it, "bigger" / "smaller" change the BHK, "plots instead" switches
  the type (and drops the BHK, which plots don't have).
* **Paging.** "show more" returns the next listings of the same search,
  skipping the ones already shown.
* **Browsing.** A search with no filters ("all listings in Surat") is shown
  newest first, with the total count.
* **Fresh start.** "new search", "start over" or "forget that" drops the
  memory.

The query parser (rules + Qwen3) still reads every message; this module
only combines its output with the previous search.  No retraining needed.

State lives in the conversation itself: the backend stores the ``search``
dict returned here on the assistant message and passes it back in
``history`` next time, so nothing is kept in this process.
"""

from __future__ import annotations

import dataclasses
import logging
import re
from typing import Any

from ai.inference.generate_response import (
    _listing_line,
    _no_results_reply,
    _pick_redirect,
    _relaxation_sentence,
)
from ai.nlu.query_parser import MAX_QUERY_CHARS, parse_query
from ai.nlu.schema import ParsedQuery
from ai.rag.retriever import listing_prices, search_parsed

logger = logging.getLogger(__name__)

PAGE_SIZE = 10
MAX_LISTED_IN_TEXT = 5  # the cards show every result; the text names the first few
_MAX_BHK = 10

# ── Follow-up phrases (English, Hinglish, a little Gujarati) ────────────────
_MORE_RE = re.compile(
    r"^\s*(?:(?:please|pls|ok|okay)\s+)?(?:show|give|send|see|load|list)?\s*(?:me\s+)?"
    r"(?:some\s+|a\s+few\s+|any\s+)?(?:more|next|others?|other\s+ones)"
    r"(?:\s+(?:results?|listings?|propert(?:y|ies)|options?|ones?|flats?|plots?))?"
    r"(?:\s+(?:please|pls))?\s*[.!?]*\s*$"
    r"|^\s*(?:aur|or|baaki|bija|vadhu)\s+(?:dikhao|dikhaiye|batao|batavo|show)\s*[.!?]*\s*$",
    re.IGNORECASE,
)
_RESET_RE = re.compile(
    r"\b(?:new search|start (?:over|again)|forget (?:that|it|this|the (?:last|previous))|reset|"
    r"something else|nayi search)\b",
    re.IGNORECASE,
)
_CHEAPER_RE = re.compile(
    r"\b(?:cheaper|less expensive|lower (?:budget|price)|budget[- ]friendly|affordable|"
    r"sast[aei]|kam (?:budget|price|kimat|daam))\b",
    re.IGNORECASE,
)
_PRICIER_RE = re.compile(
    r"\b(?:more expensive|costlier|pricier|premium|luxur(?:y|ious)|higher (?:budget|price)|mehnga)\b",
    re.IGNORECASE,
)
_BIGGER_RE = re.compile(r"\b(?:bigger|larger|more (?:bed)?rooms|spacious|bada|badi)\b", re.IGNORECASE)
_SMALLER_RE = re.compile(r"\b(?:smaller|fewer (?:bed)?rooms|less (?:bed)?rooms|compact|chhota|chhoti)\b",
                         re.IGNORECASE)
_THANKS_RE = re.compile(
    r"^\s*(?:thanks?|thank you|thx|ok(?:ay)?|great|nice|cool|perfect|good|got it|dhanyavad|shukriya|"
    r"aabhar)(?:\s+(?:a lot|so much|you))?\s*[.!]*\s*$",
    re.IGNORECASE,
)
_CHEAPEST_RE = re.compile(r"\b(?:cheapest|lowest price|price low to high|sort by price)\b", re.IGNORECASE)
_PRICIEST_RE = re.compile(r"\b(?:most expensive|highest price|price high to low)\b", re.IGNORECASE)
_NEWEST_RE = re.compile(r"\b(?:newest|latest|recent(?:ly added)?|new listings?)\b", re.IGNORECASE)


# ── (De)serialising the search state kept in the conversation ───────────────

def _filters_to_dict(pq: ParsedQuery) -> dict[str, Any]:
    d = dataclasses.asdict(pq)
    d["keywords"] = list(pq.keywords)
    return d


def _filters_from_dict(d: Any) -> ParsedQuery | None:
    if not isinstance(d, dict):
        return None
    try:
        return ParsedQuery(
            is_property_query=True,
            bhk=d.get("bhk"),
            locality=d.get("locality"),
            price_min=d.get("price_min"),
            price_max=d.get("price_max"),
            property_type=d.get("property_type"),
            keywords=tuple(d.get("keywords") or ()),
            source=d.get("source") or "rules",
        )
    except (TypeError, ValueError):
        return None


def _previous_search(history: list[dict] | None) -> dict[str, Any] | None:
    """The ``search`` state stored on the most recent assistant message, if any."""
    for msg in reversed(history or []):
        if msg.get("role") == "assistant":
            state = msg.get("search")
            return state if isinstance(state, dict) and state.get("filters") else None
    return None


# ── Combining the new message with the previous search ──────────────────────

def _round_price(value: float) -> float:
    step = 100_000 if value >= 1_000_000 else 10_000  # whole lakh / ten thousand
    return float(max(step, round(value / step) * step))


def _merge(prev: ParsedQuery, new: ParsedQuery) -> ParsedQuery:
    """Previous filters, overridden by whatever the new message states."""
    merged = dataclasses.replace(
        prev,
        is_property_query=True,
        bhk=new.bhk if new.bhk is not None else prev.bhk,
        locality=new.locality if new.locality is not None else prev.locality,
        property_type=new.property_type if new.property_type is not None else prev.property_type,
        keywords=new.keywords or prev.keywords,
        source=new.source,
    )
    if new.price_min is not None or new.price_max is not None:
        merged = dataclasses.replace(merged, price_min=new.price_min, price_max=new.price_max)
    # Plots have no bedrooms; asking for a BHK implies a flat or house.
    if new.property_type == "house_land" and new.bhk is None:
        merged = dataclasses.replace(merged, bhk=None)
    if new.bhk is not None and new.property_type is None and prev.property_type == "house_land":
        merged = dataclasses.replace(merged, property_type=None)
    return merged


def _apply_relative(message: str, pq: ParsedQuery, prev_state: dict[str, Any],
                    new: ParsedQuery) -> tuple[ParsedQuery, list[str]]:
    """Apply "cheaper" / "bigger" style changes. Returns the filters and what changed."""
    changes: list[str] = []
    stated_price = new.price_min is not None or new.price_max is not None

    if not stated_price and (_CHEAPER_RE.search(message) or _PRICIER_RE.search(message)):
        shown = prev_state.get("shown_ids") or []
        prices = listing_prices(shown) if shown else []
        if _CHEAPER_RE.search(message):
            ref = pq.price_max or (max(prices) if prices else None)
            if ref:
                pq = dataclasses.replace(pq, price_max=_round_price(ref * 0.8), price_min=None)
                changes.append("cheaper")
        else:
            ref = pq.price_max or (max(prices) if prices else None)
            if ref:
                pq = dataclasses.replace(pq, price_min=_round_price(ref), price_max=None)
                changes.append("more expensive")

    if new.bhk is None and pq.bhk is not None:
        if _BIGGER_RE.search(message) and pq.bhk < _MAX_BHK:
            pq = dataclasses.replace(pq, bhk=pq.bhk + 1)
            changes.append("bigger")
        elif _SMALLER_RE.search(message) and pq.bhk > 1:
            pq = dataclasses.replace(pq, bhk=pq.bhk - 1)
            changes.append("smaller")
    return pq, changes


def _order_for(message: str, pq: ParsedQuery) -> str:
    if _CHEAPEST_RE.search(message):
        return "price_asc"
    if _PRICIEST_RE.search(message):
        return "price_desc"
    if _NEWEST_RE.search(message) or pq.is_empty():
        return "newest"   # browsing with no filters: newest first, not arbitrary
    return "relevance"


# ── Reply text ──────────────────────────────────────────────────────────────

def _plural(n: int, word: str = "property") -> str:
    if word == "property":
        return f"{n} propert{'y' if n == 1 else 'ies'}"
    return f"{n} {word}{'' if n == 1 else 's'}"


def _reply(pq: ParsedQuery, listings: list[dict], total: int, start: int,
           is_more: bool, changes: list[str]) -> str:
    if not listings:
        if changes:
            return (f"I couldn't find anything {changes[0]}: no {pq.describe()}. "
                    "The earlier results are still the closest match.")
        if is_more:
            return (f"That's all {_plural(total)} matching {pq.describe()}. "
                    "Try a nearby locality or a wider budget to see more.")
        return _no_results_reply(pq)

    end = start + len(listings)
    has_more = end < total
    note = listings[0].get("match_note") or "exact"
    what = pq.describe() if not pq.is_empty() else "available in Surat"

    if is_more:
        head = f"Here {'is' if len(listings) == 1 else 'are'} {len(listings)} more ({start + 1}–{end} of {total}):"
    elif pq.is_empty():
        head = (f"There are {_plural(total)} available in Surat. Here are the newest "
                f"{len(listings)}. Tell me an area, budget or BHK to narrow it down:")
    else:
        lead = {"cheaper": "Here are cheaper options", "more expensive": "Here are pricier options",
                "bigger": "Here are bigger options", "smaller": "Here are smaller options"}
        if changes:
            head = f"{lead[changes[0]]}: {_plural(total)} matching {what}"
        elif note != "exact":
            head = f"I found {_plural(total)} close to what you asked for ({what})"
        else:
            head = f"I found {_plural(total)} matching {what}"
        head += "." if total <= len(listings) else f". Here are the first {len(listings)}:"

    lines = [head]
    sentence = _relaxation_sentence(note, pq) if not is_more else None
    if sentence:
        lines.append(sentence)
    for i, listing in enumerate(listings[:MAX_LISTED_IN_TEXT], start + 1):
        lines.append(_listing_line(i, listing))
    if len(listings) > MAX_LISTED_IN_TEXT:
        lines.append(f"…and {len(listings) - MAX_LISTED_IN_TEXT} more below.")
    if has_more:
        lines.append(f'{total - end} more match. Say "show more" to see them.')
    return "\n".join(lines)


# ── Public entry point ──────────────────────────────────────────────────────

def chat_turn(
    message: str,
    history: list[dict] | None = None,
    candidate_ids: list[int] | None = None,
    page_size: int = PAGE_SIZE,
) -> dict[str, Any]:
    """Answer one chat message, using earlier messages in the conversation.

    Args:
        message: The customer's new message.
        history: Earlier turns, oldest first: ``{"role", "content"}`` dicts.
            Assistant turns may carry the ``"search"`` dict this function
            returned for them; that is the conversation's memory.
        candidate_ids: Listing IDs inside a drawn map boundary, or None.
        page_size: Listings per reply.

    Returns:
        ``{"reply": str, "listings": [...], "total": int, "has_more": bool,
        "search": dict | None}``.  Listings have the same shape as
        ``search()`` results.  Store ``search`` on the assistant message and
        pass it back in ``history`` on the next turn.

    Raises:
        ValueError: If *message* is empty.
        RetrievalError: If the database or embedding fails.
    """
    if not isinstance(message, str) or not message.strip():
        raise ValueError("message must be a non-empty string.")
    message = message.strip()[:MAX_QUERY_CHARS]
    prev_state = _previous_search(history)
    prev = _filters_from_dict(prev_state["filters"]) if prev_state else None

    # "show more": same search, next page.
    if prev is not None and _MORE_RE.match(message):
        shown = [int(i) for i in prev_state.get("shown_ids") or []]
        page = search_parsed(prev, prev_state.get("embed_text") or prev.describe(),
                             candidate_ids=candidate_ids, page_size=page_size,
                             exclude_ids=shown, order=prev_state.get("order") or "relevance")
        listings = page.listings
        return {
            "reply": _reply(prev, listings, page.total, len(shown), True, []),
            "listings": listings,
            "total": page.total,
            "has_more": len(shown) + len(listings) < page.total,
            "search": {**prev_state, "shown_ids": shown + [l["id"] for l in listings]},
        }

    new = parse_query(message)
    has_filters = not new.is_empty()
    is_relative = bool(_CHEAPER_RE.search(message) or _PRICIER_RE.search(message)
                       or _BIGGER_RE.search(message) or _SMALLER_RE.search(message))
    use_memory = prev is not None and not _RESET_RE.search(message)

    if not new.is_property_query and not has_filters and not (use_memory and is_relative):
        if prev is not None and _THANKS_RE.match(message):
            reply = ("You're welcome! Tell me if you'd like to change the area, budget or BHK, "
                     'or say "show more" for more listings.')
        else:
            reply = _pick_redirect(message)
        return {"reply": reply, "listings": [], "total": 0, "has_more": False, "search": prev_state}

    pq = dataclasses.replace(new, is_property_query=True)
    changes: list[str] = []
    if use_memory:
        pq = _merge(prev, new)
        pq, changes = _apply_relative(message, pq, prev_state, new)

    order = _order_for(message, pq)
    # Rank by what the customer means overall, not just "cheaper ones".
    embed_text = message if not use_memory else f"{pq.describe()}. {message}"
    page = search_parsed(pq, embed_text, candidate_ids=candidate_ids,
                         page_size=page_size, order=order)
    listings = page.listings
    logger.info("chat_turn(): %r -> [%s]%s, %d of %d", message[:60], pq.describe(),
                " (from memory)" if use_memory else "", len(listings), page.total)
    return {
        "reply": _reply(pq, listings, page.total, 0, False, changes),
        "listings": listings,
        "total": page.total,
        "has_more": len(listings) < page.total,
        "search": {
            "filters": _filters_to_dict(pq),
            "embed_text": embed_text,
            "order": order,
            "shown_ids": [l["id"] for l in listings],
        },
    }

