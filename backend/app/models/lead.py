"""Lead ORM model — cross-team contract defined in AGENTS.md §4."""

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from app.core.database import Base

# Broker follow-up pipeline for a lead.
LEAD_STATUSES = ("new", "contacted", "visit_scheduled", "closed", "lost")


class Lead(Base):
    """A customer's explicit enquiry on a listing (``POST /listings/{id}/leads``).

    One lead per customer and listing.  Leads are never created automatically
    by chat search — being shown in a result counts as a view, not a lead.
    """

    __tablename__ = "lead"

    id = Column(Integer, primary_key=True, autoincrement=True)
    listing_id = Column(
        Integer, ForeignKey("listing.id"), nullable=False, index=True
    )
    customer_id = Column(
        Integer, ForeignKey("customer.id"), nullable=False, index=True
    )
    message = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, server_default="new")
    conversation_id = Column(
        Integer, ForeignKey("conversation.id"), nullable=True, index=True
    )
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("listing_id", "customer_id", name="uq_lead_listing_customer"),
        CheckConstraint(
            "status IN ('new', 'contacted', 'visit_scheduled', 'closed', 'lost')",
            name="ck_lead_status",
        ),
    )

    # Relationships
    listing = relationship("Listing", back_populates="leads")
    customer = relationship("Customer", back_populates="leads")

    def __repr__(self) -> str:
        return f"<Lead id={self.id} listing={self.listing_id} customer={self.customer_id}>"
