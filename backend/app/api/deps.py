"""FastAPI dependencies for authentication and authorization."""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_access_token, InvalidTokenError
from app.models.broker import Broker
from app.models.customer import Customer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Broker | Customer:
    """Decode the Bearer JWT and return the corresponding user.

    The ``sub`` claim is formatted as ``"broker:<id>"`` or
    ``"customer:<id>"``.

    Raises
    ------
    HTTPException(401)
        If the token is invalid, expired, or the user no longer exists.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_access_token(token)
    except InvalidTokenError:
        raise credentials_exception

    subject: str | None = payload.get("sub")
    if not subject or ":" not in subject:
        raise credentials_exception

    role, _, user_id_str = subject.partition(":")
    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        raise credentials_exception

    if role == "broker":
        user = db.query(Broker).filter(Broker.id == user_id).first()
    elif role == "customer":
        user = db.query(Customer).filter(Customer.id == user_id).first()
    else:
        raise credentials_exception

    if user is None:
        raise credentials_exception

    return user
