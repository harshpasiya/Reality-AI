"""FastAPI main application entrypoint."""

import logging
import math
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Warm the AI query-understanding model once at startup.

    The first model call loads Qwen3 (~24 s); doing it here means the first
    customer doesn't wait.  Skipped in PLACEHOLDER_MODE or without ``ai/``.
    """
    if not settings.PLACEHOLDER_MODE:
        try:
            from ai.nlu.query_parser import parse_query  # type: ignore[import-untyped]

            parse_query("2 bhk in vesu")
            logger.info("AI query parser warmed up")
        except ImportError:
            logger.warning("ai.nlu.query_parser not available — skipping model warm-up")
        except Exception:  # noqa: BLE001 — warm-up must never stop the API starting
            logger.exception("AI model warm-up failed")

        # Say which chat path /chat will take, so an old checkout or a broken
        # import is visible at startup instead of as "the chat forgets".
        try:
            import ai.rag.conversation  # type: ignore[import-untyped]  # noqa: F401

            logger.info("Chat mode: conversation memory ON (follow-ups, show more, totals)")
        except Exception:  # noqa: BLE001
            logger.warning(
                "Chat mode: single-message search; ai.rag.conversation failed to import",
                exc_info=True,
            )
    yield


app = FastAPI(
    title="Reality AI Backend API",
    version="1.1.0",
    description="Backend service for Reality AI — AI-powered real estate exploration platform in Surat, Gujarat.",
    lifespan=lifespan,
)

# CORS: allowed frontend origins come from CORS_ORIGINS (comma-separated).
# Auth uses Bearer tokens, not cookies, so credentials are not needed.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(SQLAlchemyError)
def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    """Handle database errors gracefully without leaking SQL internals."""
    logger.error("Database error occurred while processing %s %s: %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "A database error occurred while processing your request."},
    )


def _json_safe(value):
    """Replace NaN / infinity (not valid JSON) with their string form."""
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


@app.exception_handler(RequestValidationError)
def validation_exception_handler(request: Request, exc: RequestValidationError):
    """FastAPI's default 422 echoes the input back; a NaN coordinate in it
    can't be encoded as JSON and turned the 422 into a 500."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": _json_safe(jsonable_encoder(exc.errors(), custom_encoder={
            ValueError: str,
        }))},
    )


@app.get("/", tags=["Health"])
def health_check() -> dict[str, str]:
    """Basic health check endpoint."""
    return {"status": "ok"}


# Listing photos (POST /listings/{id}/images) are served from here.
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")


# ── Routers ──────────────────────────────────────────────────────────────
from app.api.routes import (  # noqa: E402
    analytics,
    auth,
    boundary_search,
    brokers,
    chat,
    leads,
    listings,
    localities,
)

app.include_router(auth.router)
app.include_router(listings.router)
app.include_router(leads.router)
app.include_router(chat.router)
app.include_router(boundary_search.router)
app.include_router(analytics.router)
app.include_router(brokers.router)
app.include_router(localities.router)
