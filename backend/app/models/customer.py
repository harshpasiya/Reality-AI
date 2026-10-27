"""Customer ORM model — cross-team contract defined in AGENTS.md §4."""

from sqlalchemy import Column, DateTime, Integer, String, func
from sqlalchemy.orm import relationship

from app.core.database import Base


class Customer(Base):
    """A customer who searches properties and interacts via chat.

    NOTE: Customers currently require an email — confirm this design choice
    with the team rather than assuming it's final (some flows may support
    anonymous/guest usage later).
    """

    __tablename__ = "customer"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    conversations = relationship("Conversation", back_populates="customer")
    leads = relationship("Lead", back_populates="customer")

    def __repr__(self) -> str:
        return f"<Customer id={self.id} email={self.email!r}>"
