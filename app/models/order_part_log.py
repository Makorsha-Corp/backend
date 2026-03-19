"""Order item log model (legacy audit trail)"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base_class import Base


class OrderPartLog(Base):
    """Order item log model for audit trail (legacy)"""

    __tablename__ = "order_parts_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    order_part_id = Column(Integer, ForeignKey("order_items.id"), nullable=False)  # Fixed: order_parts → order_items
    action_on = Column(String, nullable=False)
    before = Column(Text, nullable=False)
    after = Column(Text, nullable=False)
    updated_by = Column(Integer, ForeignKey("profiles.id"), nullable=False)
    updated_on = Column(DateTime, nullable=False, default=datetime.utcnow)
    note = Column(Text, nullable=True)

    # Relationships
    order_item = relationship("OrderItem", backref="logs")  # Fixed: OrderPart → OrderItem
    updated_by_user = relationship("Profile", backref="order_part_logs")
