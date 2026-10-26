"""Authentication routes — POST /auth/register and POST /auth/login."""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.security import create_access_token
from app.models.broker import Broker
from app.schemas.auth import AuthUser, RegisterRequest, TokenResponse, UserResponse
from app.services.auth_service import (
    DuplicateEmailError,
    authenticate_user,
    register_user,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Authentication"])


def _get_role(user: object) -> str:
    """Determine role based on ORM instance type."""
    return "broker" if isinstance(user, Broker) else "customer"


def _make_subject(user: object) -> str:
    """Build the JWT ``sub`` claim in ``role:id`` format."""
    return f"{_get_role(user)}:{user.id}"  # type: ignore[attr-defined]


def _build_auth_user(user: object) -> AuthUser:
    """Build the AuthUser schema from an ORM model instance."""
    return AuthUser(
        id=user.id,  # type: ignore[attr-defined]
        email=user.email,  # type: ignore[attr-defined]
        name=user.name,  # type: ignore[attr-defined]
        role=_get_role(user),  # type: ignore[arg-type]
    )


@router.post(
    "/auth/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new broker or customer account",
)
def register(
    body: RegisterRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Create a new user and return a JWT on success."""
    try:
        user = register_user(
            db,
            email=body.email,
            password=body.password,
            name=body.name,
            role=body.role,
            phone=body.phone,
        )
    except DuplicateEmailError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    token = create_access_token(subject=_make_subject(user))
    logger.info("Registered %s id=%s", body.role, user.id)  # type: ignore[attr-defined]
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=_build_auth_user(user),
    )


@router.post(
    "/auth/login",
    response_model=TokenResponse,
    summary="Log in and receive a JWT",
)
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Authenticate a user via email + password.

    Uses FastAPI's ``OAuth2PasswordRequestForm`` so the Swagger UI
    "Authorize" button works out of the box.
    """
    user = authenticate_user(db, email=form.username, password=form.password)
    if user is None:
        # Generic message — don't reveal whether the email exists
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(subject=_make_subject(user))
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        user=_build_auth_user(user),
    )


@router.get(
    "/auth/me",
    response_model=UserResponse,
    summary="Return the currently authenticated user's profile",
)
def me(
    current_user=Depends(get_current_user),
) -> UserResponse:
    """Fetch the profile of the user identified by the Bearer JWT."""
    return UserResponse(
        id=current_user.id,
        name=current_user.name,
        email=current_user.email,
        role=_get_role(current_user),  # type: ignore[arg-type]
        created_at=current_user.created_at,
        phone=getattr(current_user, "phone", None),
    )
