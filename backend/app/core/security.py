"""Password hashing, JWT creation/verification, and related security utilities."""

from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# ---------------------------------------------------------------------------
# Password hashing (bcrypt via passlib)
# ---------------------------------------------------------------------------

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Return a bcrypt hash of *password*."""
    return _pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """Return ``True`` if *plain* matches *hashed*."""
    return _pwd_context.verify(plain, hashed)


# ---------------------------------------------------------------------------
# JWT tokens (python-jose)
# ---------------------------------------------------------------------------


class InvalidTokenError(Exception):
    """Raised when a JWT cannot be decoded or has expired.

    Wraps python-jose's raw exceptions so callers don't need to import
    ``jose`` directly.
    """


def create_access_token(
    subject: str,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed JWT with ``sub`` and ``exp`` claims.

    Parameters
    ----------
    subject:
        Value to embed as the ``sub`` claim (typically ``"broker:<id>"`` or
        ``"customer:<id>"``).
    expires_delta:
        Custom lifetime; defaults to ``settings.JWT_EXPIRE_MINUTES``.
    """
    expire = datetime.now(timezone.utc) + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    )
    to_encode = {"sub": subject, "exp": expire}
    return jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> dict:
    """Decode and verify a JWT, returning its payload dict.

    Raises
    ------
    InvalidTokenError
        On any verification failure (expired, bad signature, malformed).
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except JWTError as exc:
        raise InvalidTokenError(str(exc)) from exc
