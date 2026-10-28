"""Chat route — POST /chat (AI RAG orchestration + conversation tracking)."""

from datetime import datetime, timezone
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.api.deps import get_current_user
from app.api.routes.boundary_search import boundary_listing_ids
from app.core.config import settings
from app.core.database import get_db
from app.models.conversation import Conversation
from app.models.customer import Customer
from app.models.listing import Listing, VISIBLE_STATUSES
from app.schemas.chat import (
    ChatHistoryResponse,
    ChatListing,
    ChatMessageResponse,
    ChatRequest,
    ChatResponse,
)
from app.schemas.listing import ListingResponse
from app.services import geo_service, listing_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Chat"])

TOP_K = 5
# Listings per reply when the conversation-aware chat (ai.rag.conversation) runs.
PAGE_SIZE = 10


class _NeverRaised(Exception):
    """Placeholder for an AI exception class that isn't defined."""


# ---------------------------------------------------------------------------
# AI layer calls (AGENTS.md §5)
# ---------------------------------------------------------------------------


def _fallback_search(
    db: Session, candidate_ids: list[int] | None
) -> list[dict]:
    """Isolated-development stand-in for ``search()`` (no ``ai/`` package).

    Returns dicts in the same shape as the real ``search()`` so the rest of
    the route has one code path.  The listings are NOT ranked by relevance.
    """
    if candidate_ids is not None and not candidate_ids:
        return []
    query = db.query(Listing).filter(Listing.status.in_(VISIBLE_STATUSES))
    if candidate_ids is not None:
        query = query.filter(Listing.id.in_(candidate_ids))
    rows = query.order_by(Listing.created_at.desc(), Listing.id.desc()).limit(TOP_K).all()
    return [
        {
            "id": l.id,
            "title": l.title,
            "price": float(l.price),
            "property_type": l.property_type,
            "bhk": (l.rooms or {}).get("bedrooms"),
            "match_note": None,
        }
        for l in rows
    ]


def _search(db: Session, message: str, candidate_ids: list[int] | None) -> list[dict]:
    """Call ``ai.rag.retriever.search()``; returns a list of dicts.

    ``ValueError`` → 422; ``RetrievalError`` (or any other failure) → 503.
    No silent fallback to unrelated listings when the real search fails.
    """
    try:
        from ai.rag import retriever  # type: ignore[import-untyped]
    except ImportError:
        logger.warning("ai.rag.retriever not available — using unranked DB fallback")
        return _fallback_search(db, candidate_ids)
    except Exception:
        # Installed but broken at import (e.g. RuntimeError: DATABASE_URL unset,
        # model files missing) — that is an outage, not "no AI package".
        logger.exception("ai.rag.retriever failed to import")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search is temporarily unavailable",
        )

    retrieval_error = getattr(retriever, "RetrievalError", _NeverRaised)
    try:
        return list(retriever.search(message, candidate_ids=candidate_ids, top_k=TOP_K))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except retrieval_error:
        logger.exception("AI search failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search is temporarily unavailable",
        )
    except Exception:
        logger.exception("Unexpected error from AI search")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search is temporarily unavailable",
        )


def _chat_turn(
    message: str, history: list[dict], candidate_ids: list[int] | None
) -> dict | None:
    """Call ``ai.rag.conversation.chat_turn()``; None when that module isn't installed.

    It remembers the search across messages ("cheaper", "what about Adajan?",
    "show more").  Without it the route falls back to the single-message
    ``search()`` + ``generate_response()`` pair.  Errors map like ``_search``.
    """
    if settings.PLACEHOLDER_MODE:
        return None
    try:
        from ai.rag.conversation import chat_turn  # type: ignore[import-untyped]
        from ai.rag import retriever  # type: ignore[import-untyped]
    except ImportError:
        return None
    except Exception:
        logger.exception("ai.rag.conversation failed to import")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search is temporarily unavailable",
        )

    retrieval_error = getattr(retriever, "RetrievalError", _NeverRaised)
    try:
        return chat_turn(message, history, candidate_ids=candidate_ids, page_size=PAGE_SIZE)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except retrieval_error:
        logger.exception("AI search failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search is temporarily unavailable",
        )
    except Exception:
        logger.exception("Unexpected error from AI chat")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Search is temporarily unavailable",
        )


def _generate_response(message: str, results: list[dict], history: list[dict]) -> str:
    """Reply text — placeholder text when ``PLACEHOLDER_MODE`` is True.

    ``generate_response()`` never raises (AGENTS.md §5); it returns its own
    fallback sentence on internal errors.
    """
    if settings.PLACEHOLDER_MODE:
        if not results:
            return (
                f"[PLACEHOLDER MODE] I reviewed your query '{message}', "
                "but found no matching properties in Surat."
            )
        titles = ", ".join(f"'{r.get('title', 'Listing ' + str(r['id']))}'" for r in results)
        return (
            f"[PLACEHOLDER MODE] Based on your query '{message}', "
            f"here are relevant properties in Surat: {titles}."
        )

    try:
        from ai.inference import generate_response  # type: ignore[import-untyped]
    except Exception as exc:  # ImportError, or a module that fails while importing
        log = logger.warning if isinstance(exc, ImportError) else logger.exception
        log("ai.inference not available — returning fallback response despite PLACEHOLDER_MODE=False")
        titles = ", ".join(f"'{r.get('title', r['id'])}'" for r in results) if results else "none"
        return f"Found relevant listings: {titles}."

    return generate_response(message, results, history)


def _locked_conversation(db: Session, conversation_id: int, customer_id: int) -> Conversation | None:
    """Load the conversation with a row lock, so concurrent appends can't drop messages."""
    return (
        db.query(Conversation)
        .filter(
            Conversation.id == conversation_id,
            Conversation.customer_id == customer_id,
        )
        .with_for_update()
        .populate_existing()
        .first()
    )


def _append_message(conversation: Conversation, message: dict) -> None:
    conversation.messages = list(conversation.messages or []) + [message]
    flag_modified(conversation, "messages")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Customer chat message — orchestrates RAG and LLM inference",
)
def chat(
    body: ChatRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ChatResponse:
    """Save the message, run AI search + reply, save the reply.

    The user message is committed before the AI runs, so it is kept even if
    search fails with 503.  The row lock is held only while appending, never
    during the (possibly ~8 s) model call.  Listings shown here count as
    views; leads are created only by ``POST /listings/{id}/leads``.
    """
    if not isinstance(current_user, Customer):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only customers can initiate or participate in chat sessions",
        )

    # 1-2. Load or create the conversation and append the user message
    user_msg = {"role": "user", "content": body.message, "timestamp": _now_iso()}
    if body.conversation_id:
        conversation = _locked_conversation(db, body.conversation_id, current_user.id)
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Conversation {body.conversation_id} not found",
            )
        # history = earlier turns only, in the contract's {role, content, timestamp} shape
        history = [
            {k: m.get(k) for k in ("role", "content", "timestamp")}
            for m in conversation.messages or []
        ]
        # The conversation-aware chat also reads the search state stored on replies.
        memory = [
            {k: m.get(k) for k in ("role", "content", "search")}
            for m in conversation.messages or []
        ]
        _append_message(conversation, user_msg)
    else:
        history, memory = [], []
        conversation = Conversation(customer_id=current_user.id, messages=[user_msg])
        db.add(conversation)
    db.commit()
    conversation_id = conversation.id

    # 3-4. Narrow by drawn polygon, then AI search (list of dicts, ranked)
    candidate_ids = (
        boundary_listing_ids(db, body.polygon) if body.polygon else None
    )
    turn = _chat_turn(body.message, memory, candidate_ids)
    if turn is not None:
        results, reply_text = turn["listings"], turn["reply"]
        total, has_more, search_state = turn["total"], turn["has_more"], turn["search"]
    else:
        results = _search(db, body.message, candidate_ids)
        # 5. Reply (off-topic messages: results == [] and a polite redirect)
        reply_text = _generate_response(body.message, results, history)
        total, has_more, search_state = None, False, None

    # Build API listings from the DB rows the results point to, in AI order;
    # sold / withdrawn listings are dropped even if the AI returned them.
    rows = {
        l.id: l
        for l in geo_service.visible_listings_by_ids(db, [r["id"] for r in results])
    }
    listings = [
        ChatListing.model_validate(rows[r["id"]]).model_copy(
            update={
                "bhk": r.get("bhk"),
                "match_note": r.get("match_note"),
                "distance_score": r.get("distance_score"),
            }
        )
        for r in results
        if r["id"] in rows
    ]

    # 6. Append the assistant message under the lock again, record views
    conversation = _locked_conversation(db, conversation_id, current_user.id)
    _append_message(
        conversation,
        {
            "role": "assistant",
            "content": reply_text,
            "timestamp": _now_iso(),
            "listing_ids": [l.id for l in listings],
            "match_notes": [l.match_note for l in listings],
            "has_more": has_more,
            "search": search_state,
        },
    )
    listing_service.record_views(db, [l.id for l in listings])
    db.commit()

    return ChatResponse(
        conversation_id=conversation_id,
        reply=reply_text,
        listings=listings,
        total=total,
        has_more=has_more,
    )


@router.get(
    "/chat/{conversation_id}",
    response_model=ChatHistoryResponse,
    summary="Fetch the full chat history for a conversation",
)
def get_chat_history(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
) -> ChatHistoryResponse:
    """Return the complete message history for the given conversation.

    Only the owning customer may access their conversation.
    """
    if not isinstance(current_user, Customer):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only customers can view chat history",
        )

    conversation = (
        db.query(Conversation)
        .filter(
            Conversation.id == conversation_id,
            Conversation.customer_id == current_user.id,
        )
        .first()
    )
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation {conversation_id} not found",
        )

    raw_messages = conversation.messages or []

    # Collect all listing IDs referenced by assistant messages (handling int or string IDs)
    all_listing_ids: set[int] = set()
    for msg in raw_messages:
        lids = msg.get("listing_ids") or []
        for lid in lids:
            try:
                all_listing_ids.add(int(lid))
            except (ValueError, TypeError):
                pass

    # Batch-load listings from DB in a single query
    listings_map: dict[int, ListingResponse] = {}
    if all_listing_ids:
        db_listings = (
            db.query(Listing).filter(Listing.id.in_(all_listing_ids)).all()
        )
        for l in db_listings:
            listings_map[l.id] = ListingResponse.model_validate(l)

    parsed_messages: list[ChatMessageResponse] = []

    for msg in raw_messages:
        role = msg.get("role", "user")
        sender = role if role in ("user", "assistant") else "user"
        content = msg.get("content", "")
        ts_raw = msg.get("timestamp")

        # Parse timestamp — stored as ISO-8601 string
        if ts_raw:
            try:
                ts = datetime.fromisoformat(ts_raw)
            except (ValueError, TypeError):
                ts = datetime.now(timezone.utc)
        else:
            ts = datetime.now(timezone.utc)

        # Attach listings for assistant messages using stored IDs
        msg_lids = []
        for lid in msg.get("listing_ids", []):
            try:
                msg_lids.append(int(lid))
            except (ValueError, TypeError):
                pass

        msg_listings = [
            listings_map[lid]
            for lid in msg_lids
            if lid in listings_map
        ]

        parsed_messages.append(
            ChatMessageResponse(
                sender=sender,
                message=content,
                timestamp=ts,
                listings=msg_listings,
                has_more=bool(msg.get("has_more")),
            )
        )

    # Return top-level listings as well so frontend gets all conversation listings
    return ChatHistoryResponse(
        conversation_id=conversation.id,
        user_id=conversation.customer_id,
        messages=parsed_messages,
        listings=list(listings_map.values()),
    )
