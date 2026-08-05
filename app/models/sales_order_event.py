"""Sales order event model - immutable activity log for a sales order."""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base_class import Base


class SalesOrderEvent(Base):
    """
    Append-only activity log for a sales order.
    event_type: 'created', 'approved', 'approval_withdrawn', section confirm/unconfirm
    events, 'invoice_confirmed', 'order_completed', etc.
    """

    __tablename__ = "sales_order_events"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    sales_order_id = Column(Integer, ForeignKey("sales_orders.id", ondelete="CASCADE"), nullable=False, index=True)

    event_type = Column(String(50), nullable=False)
    description = Column(Text, nullable=False)
    metadata_json = Column("metadata", JSON, nullable=True)

    performed_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    performer = relationship("Profile", foreign_keys=[performed_by])
