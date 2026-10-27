"""Authentication service — registration and login business logic."""

from typing import Literal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.security import hash_password, verify_password
from app.models.broker import Broker
from app.models.customer import Customer
from app.schemas.auth import normalise_email


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class DuplicateEmailError(Exception):
    """Raised when attempting to register with an email that already exists."""


# ---------------------------------------------------------------------------
# Service functions
# ---------------------------------------------------------------------------


def _find_by_email(db: Session, model_cls, email: str):
    """Case-insensitive lookup, so accounts stored before normalisation still match."""
    return db.query(model_cls).filter(func.lower(model_cls.email) == email).first()


def register_user(
    db: Session,
    email: str,
    password: str,
    name: str,
    role: Literal["broker", "customer"],
    phone: str | None = None,
) -> Broker | Customer:
    """Create a new broker or customer account.

    Parameters
    ----------
    db:
        Active database session.
    email:
        Must be unique across both the broker and customer tables
        (compared case-insensitively; stored lower-cased).
    password:
        Plain-text; hashed before storage.
    name:
        Display name.
    role:
        ``"broker"`` or ``"customer"`` — determines the target table.
    phone:
        Broker business phone in E.164 form; ignored for customers.

    Returns
    -------
    Broker | Customer
        The newly created ORM instance.

    Raises
    ------
    DuplicateEmailError
        If a broker or customer with the same email already exists.
    """
    email = normalise_email(email)
    if _find_by_email(db, Broker, email) or _find_by_email(db, Customer, email):
        raise DuplicateEmailError(f"An account with email {email!r} already exists")

    hashed = hash_password(password)

    if role == "broker":
        user = Broker(name=name, email=email, password_hash=hashed, phone=phone)
    else:
        user = Customer(name=name, email=email, password_hash=hashed)

    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(
    db: Session,
    email: str,
    password: str,
) -> Broker | Customer | None:
    """Verify credentials and return the user, or ``None`` on failure.

    Security note: we intentionally do NOT distinguish between
    "no such user" and "wrong password" in the return value or in any
    eventual error message — this prevents user-enumeration attacks.
    """
    email = normalise_email(email)
    # Try broker first, then customer (registration keeps emails unique across both)
    for model_cls in (Broker, Customer):
        user = _find_by_email(db, model_cls, email)
        if user is not None:
            if user.password_hash and verify_password(password, user.password_hash):
                return user
            return None  # found the email but password wrong — don't leak which

    return None  # no user found at all — same return shape
