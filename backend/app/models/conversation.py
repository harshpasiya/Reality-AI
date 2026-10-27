"""Conversation ORM model — cross-team contract defined in AGENTS.md §4."""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, func
from sqlalchemy.orm import relationship

from app.core.database import Base


class Conversation(Base):
    """A chat conversation between a customer and the AI assistant.

    ``messages`` stores a JSON array of ``{role, content, timestamp}`` objects
    matching the shape specified in AGENTS.md §4.
    """

    __tablename__ = "conversation"

    id = Column(Integer, primary_key=True, autoincrement=True)
    customer_id = Column(
        Integer, ForeignKey("customer.id"), nullable=False, index=True
    )
    messages = Column(JSON, nullable=True, default=list)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    customer = relationship("Customer", back_populates="conversations")

    def __repr__(self) -> str:
        return f"<Conversation id={self.id} customer_id={self.customer_id}>"
