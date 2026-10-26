"""Broker ORM model — cross-team contract defined in AGENTS.md §4."""

from sqlalchemy import Column, DateTime, Integer, String, func
from sqlalchemy.orm import relationship

from app.core.database import Base


class Broker(Base):
    """A real-estate broker who publishes and manages property listings.

    ``phone`` is the broker's business number in E.164 form.  It is never
    included in public listing responses — only the broker themselves and a
    customer who has created a lead on one of the broker's listings see it.
    ``phone_hash`` (frozen contract field) is kept alongside it.
    ``password_hash`` is bcrypt-hashed via passlib.
    """

    __tablename__ = "broker"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    phone_hash = Column(String, nullable=True)
    phone = Column(String(20), nullable=True)
    password_hash = Column(String, nullable=False)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    listings = relationship("Listing", back_populates="broker")

    def __repr__(self) -> str:
        return f"<Broker id={self.id} email={self.email!r}>"
