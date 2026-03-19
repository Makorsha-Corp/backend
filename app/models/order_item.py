"""Order item model (represents items in an order)"""
from sqlalchemy import Column, Integer, Numeric, Boolean, String, DateTime, ForeignKey, Text, Enum
from sqlalchemy.orm import relationship
from app.db.base_class import Base
from app.models.enums import UnstableTypeEnum


class OrderItem(Base):
    """Order item model - represents items in an order"""

    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False, index=True)
    qty = Column(Integer, nullable=False)
    unit_cost = Column(Numeric(15, 2), nullable=True)
    note = Column(Text, nullable=True)
    vendor_id = Column(Integer, ForeignKey("vendors.id"), nullable=True)
    brand = Column(String, nullable=True)
    office_note = Column(Text, nullable=True)
    mrr_number = Column(String, nullable=True)

    # Boolean flags for approval workflow
    approved_pending_order = Column(Boolean, nullable=False, default=False)
    approved_office_order = Column(Boolean, nullable=False, default=False)
    approved_budget = Column(Boolean, nullable=False, default=False)
    approved_storage_withdrawal = Column(Boolean, nullable=False, default=False)
    in_storage = Column(Boolean, nullable=False, default=False)
    is_deleted = Column(Boolean, nullable=False, default=False)

    # Sample tracking
    is_sample_sent_to_office = Column(Boolean, nullable=False, default=False)
    is_sample_received_by_office = Column(Boolean, nullable=False, default=False)

    # Dates
    part_sent_by_office_date = Column(DateTime, nullable=True)
    part_received_by_factory_date = Column(DateTime, nullable=True)
    part_purchased_date = Column(DateTime, nullable=True)
    deleted_at = Column(DateTime, nullable=True)

    # Storage tracking
    qty_taken_from_storage = Column(Integer, nullable=False, default=0)

    # Unstable type
    unstable_type = Column(Enum(UnstableTypeEnum), nullable=True)

    # Relationships
    order = relationship("Order", backref="order_items")
    item = relationship("Item", backref="order_items")
    vendor = relationship("Vendor", backref="order_items")
