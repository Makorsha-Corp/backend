"""Purchase order event model - immutable activity log for a PO."""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base_class import Base


class PurchaseOrderEvent(Base):
    """
    Append-only activity log for a purchase order.
    event_type: 'created', 'received', 'approved', 'approval_withdrawn',
    'details_updated', 'notes_updated', section lock events, etc.
    """

    __tablename__ = "purchase_order_events"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    purchase_order_id = Column(Integer, ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False, index=True)

    event_type = Column(String(50), nullable=False)
    description = Column(Text, nullable=False)

    performed_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    performer = relationship("Profile", foreign_keys=[performed_by])
