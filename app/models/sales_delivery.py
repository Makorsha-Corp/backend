"""Sales delivery model - tracks individual deliveries for sales orders"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Date
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base_class import Base


class SalesDelivery(Base):
    """
    Individual deliveries for sales orders.
    One sales order can have multiple deliveries over time.
    """

    __tablename__ = "sales_deliveries"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    sales_order_id = Column(Integer, ForeignKey("sales_orders.id", ondelete="CASCADE"), nullable=False, index=True)

    # === REFERENCE ===
    delivery_number = Column(String(100), nullable=False, unique=True, index=True)
    # Auto-generated: DEL-2025-001

    # === DATES ===
    scheduled_date = Column(Date, nullable=True)
    actual_delivery_date = Column(Date, nullable=True)

    # === STATUS ===
    delivery_status = Column(String(50), nullable=False, default='planned', index=True)
    # 'planned' | 'delivered' | 'cancelled'

    # === SHIPPING ===
    tracking_number = Column(String(255), nullable=True)

    # === NOTES ===
    notes = Column(Text, nullable=True)

    # === AUDIT ===
    created_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime, nullable=True, onupdate=datetime.utcnow)

    # === RELATIONSHIPS ===
    sales_order = relationship("SalesOrder", backref="deliveries")
    creator = relationship("Profile", foreign_keys=[created_by], backref="created_sales_deliveries")
    updater = relationship("Profile", foreign_keys=[updated_by], backref="updated_sales_deliveries")
    workspace = relationship("Workspace", backref="sales_deliveries")
