"""Prompt assembly for the Reality AI chat assistant.

This module owns everything about *how* a query, retrieved listings, and
conversation history get turned into the actual text/messages sent to the
fine-tuned model. Keeping this separate from generate_response.py means the
prompt design can be iterated on (Phase 5 evaluation/tuning) without
touching model-loading or generation-call code at all.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------
# Deliberately explicit about scope and grounding — these are the two
# failure modes manual review needs to watch for in Phase 3/5: the model
# inventing details not in the retrieved listings, and the model answering
# off-topic questions instead of redirecting.
SYSTEM_PROMPT = """You are the Reality AI property assistant, a friendly and knowledgeable \
real estate guide for a property search platform. Your job is to help customers find \
properties in Surat that match what they're looking for.

Rules you must always follow:
1. Only describe properties using the listing information given to you in this \
conversation's context. Never invent a price, location, feature, or amenity that isn't \
explicitly present in the provided listings — if you don't know something about a \
listing, say so rather than guessing.
2. If no listings are provided, or none of the provided listings are a good match, say \
so honestly instead of pretending one fits.
3. Mention nearby amenities (schools, hospitals, restaurants, transit, parks) only when \
the customer's question is actually about what's nearby — don't volunteer amenity \
details unprompted.
4. You only help with real estate and property search. If asked about anything \
unrelated (general knowledge, coding help, personal advice, or anything else outside \
property search), politely decline and steer the conversation back — for example: \
"I'm here to help you find a property — is there something about your search I can \
help with?" or "That's outside what I can help with, but I'd be happy to help you find \
a home instead."
5. Keep responses conversational and concise. Don't dump raw data or list every field \
of every listing — describe properties the way a helpful human agent would.
"""

# Keyword/phrase heuristic for deciding whether a query is asking about
# nearby amenities. Deliberately over-inclusive rather than under —
# missing an amenity question means a customer's "is this near a school?"
# gets a generic reply, which is a worse failure than occasionally
# including amenities context the model doesn't end up using.
_AMENITY_KEYWORDS = (
    "school", "schools", "hospital", "hospitals", "clinic", "restaurant",
    "restaurants", "cafe", "transit", "station", "bus stop", "metro",
    "park", "parks", "nearby", "near by", "close to", "walking distance",
    "around the area", "in the vicinity", "what's around", "whats around",
    "surrounding area", "neighbourhood", "neighborhood", "amenities",
    "facilities", "convenient to", "how far", "distance to",
)


def is_amenity_related(query: str) -> bool:
    """Heuristic check: is this query asking about nearby amenities?

    This is intentionally a simple keyword/phrase match, not an NLU
    classifier — false positives (occasionally including amenities context
    for a borderline query) are cheap; false negatives (never surfacing
    amenities when genuinely asked) are the failure mode worth avoiding.
    If this heuristic proves too narrow or too broad during Phase 5
    evaluation, replace it with something more robust then — it's isolated
    to this one function on purpose.

    Args:
        query: The customer's raw query text.

    Returns:
        True if the query appears to be asking about nearby amenities.
    """
    if not query:
        return False
    lowered = query.lower()
    return any(kw in lowered for kw in _AMENITY_KEYWORDS)


def _format_price(price: float | None) -> str:
    if price is None:
        return "price not listed"
    if price >= 1_00_00_000:  # 1 crore
        return f"Rs.{price / 1_00_00_000:.2f} Cr"
    if price >= 1_00_000:  # 1 lakh
        return f"Rs.{price / 1_00_000:.1f} L"
    return f"Rs.{price:,.0f}"


def _format_amenity_entry(entry: dict) -> str:
    """Format one cached amenity place: name, rating if present, distance."""
    name = entry.get("name", "Unknown")
    distance_m = entry.get("distance_m")
    rating = entry.get("rating")
    user_ratings_total = entry.get("user_ratings_total") or 0

    parts = [name]
    if rating is not None:
        rating_str = f"{rating:.1f}\u2605"
        if user_ratings_total:
            rating_str += f" ({user_ratings_total} reviews)"
        parts.append(rating_str)
    if distance_m is not None:
        if distance_m >= 1000:
            parts.append(f"{distance_m / 1000:.1f}km")
        else:
            parts.append(f"{distance_m:.0f}m")
    return " \u00b7 ".join(parts)


_AMENITY_CATEGORY_LABELS = {
    "schools": "Schools",
    "hospitals": "Hospitals",
    "restaurants": "Restaurants",
    "transit": "Transit",
    "parks": "Parks",
}


def _build_amenities_summary(amenities: dict | None) -> str | None:
    """Build a short readable amenities summary, or None if nothing to show."""
    if not amenities:
        return None

    lines = []
    for category, label in _AMENITY_CATEGORY_LABELS.items():
        entries = amenities.get(category) or []
        if not entries:
            continue
        # Highest-rated first when any entry has a rating; unrated last.
        entries_sorted = sorted(
            entries, key=lambda e: (e.get("rating") is None, -(e.get("rating") or 0))
        )
        formatted = ", ".join(_format_amenity_entry(e) for e in entries_sorted[:3])
        lines.append(f"{label}: {formatted}")

    if not lines:
        return None
    return "Nearby: " + "; ".join(lines)


def format_listing_context(listings: list[dict], query: str) -> str:
    """Format retrieved listings into readable text for the model's context.

    Amenities are only included when `is_amenity_related(query)` is True —
    otherwise the context stays focused on core listing details, per the
    system prompt's rule against volunteering amenity info unprompted.

    Args:
        listings: Listings as returned by ai.rag.retriever.search() — each
            a dict with title, description, price, property_type, lat,
            lng, amenities, distance_score.
        query: The customer's current query, used to decide whether to
            include amenities.

    Returns:
        A formatted string block. Explicitly notes when there are no
        matching listings, rather than returning an empty string.
    """
    if not listings:
        return "No matching properties were found for this search."

    include_amenities = is_amenity_related(query)
    blocks = []
    for listing in listings:
        title = listing.get("title", "Untitled listing")
        description = listing.get("description") or ""
        if len(description) > 200:
            description = description[:197] + "..."
        price = _format_price(listing.get("price"))
        ptype = listing.get("property_type", "unknown")

        block_lines = [f"- {title} ({ptype}, {price})"]
        if description:
            block_lines.append(f"  {description}")

        if include_amenities:
            summary = _build_amenities_summary(listing.get("amenities"))
            if summary:
                block_lines.append(f"  {summary}")
            elif listing.get("amenities") is None:
                # Only mention absence when the customer actually asked —
                # matches format_listing_context's contract, not a
                # generic disclaimer shown on every listing.
                block_lines.append("  (Amenities data not yet available for this listing)")

        blocks.append("\n".join(block_lines))

    return "\n\n".join(blocks)


def format_history(history: list[dict] | None, max_turns: int = 6) -> str:
    """Format recent conversation history for inclusion in the prompt.

    Only the most recent `max_turns` entries are kept — older turns are
    dropped since the model's context window is limited, and recency
    matters far more than completeness for a follow-up-style conversation.

    Args:
        history: List of {"role": "user"|"assistant", "content": str}
            dicts, oldest first. May be None or empty.
        max_turns: Maximum number of most-recent turns to include.

    Returns:
        A formatted string, or an empty string if there's no history.
    """
    if not history:
        return ""

    recent = history[-max_turns:]
    lines = []
    for turn in recent:
        role = turn.get("role", "user")
        content = turn.get("content", "")
        label = "Customer" if role == "user" else "Assistant"
        lines.append(f"{label}: {content}")
    return "\n".join(lines)


# Rough token budget for the combined history + listing context, before the
# system prompt and the current query. This is intentionally conservative —
# see the comment at its use site for what happens when it's exceeded.
_MAX_CONTEXT_CHARS = 12_000  # ~3000 tokens at a rough 4 chars/token estimate


def build_prompt(query: str, listings: list[dict], history: list[dict] | None) -> list[dict]:
    """Assemble the full chat-format message list for the model.

    Args:
        query: The customer's current message.
        listings: Retrieved listings from ai.rag.retriever.search().
        history: Prior conversation turns, oldest first.

    Returns:
        A list of {"role": ..., "content": ...} dicts suitable for
        tokenizer.apply_chat_template().
    """
    listing_context = format_listing_context(listings, query)
    history_text = format_history(history)

    # If the combined context is clearly too large, trim listings first
    # (keep the top 3 — they're already ranked by relevance from
    # retriever.search()) before trimming history further. Listings carry
    # more of the "can we actually answer this" signal than older turns do.
    if len(listing_context) + len(history_text) > _MAX_CONTEXT_CHARS and len(listings) > 3:
        logger.warning(
            "Prompt context exceeds budget (%d chars) — trimming listings from %d to 3.",
            len(listing_context) + len(history_text), len(listings),
        )
        listing_context = format_listing_context(listings[:3], query)
        if len(listing_context) + len(history_text) > _MAX_CONTEXT_CHARS:
            history_text = format_history(history, max_turns=2)

    user_content_parts = []
    if history_text:
        user_content_parts.append(f"Conversation so far:\n{history_text}")
    user_content_parts.append(f"Available properties:\n{listing_context}")
    user_content_parts.append(f"Customer's question: {query}")

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "\n\n".join(user_content_parts)},
    ]
