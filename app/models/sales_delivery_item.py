"""Sales delivery item model - line items in each delivery"""
from sqlalchemy import Column, Integer, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class SalesDeliveryItem(Base):
    """
    Line items in sales deliveries.
    Links back to sales order items and tracks what was delivered.
    """

    __tablename__ = "sales_delivery_items"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    delivery_id = Column(Integer, ForeignKey("sales_deliveries.id", ondelete="CASCADE"), nullable=False, index=True)
    sales_order_item_id = Column(Integer, ForeignKey("sales_order_items.id", ondelete="RESTRICT"), nullable=False, index=True)
    item_id = Column(Integer, ForeignKey("items.id", ondelete="RESTRICT"), nullable=False, index=True)

    # === QUANTITY ===
    quantity_delivered = Column(Integer, nullable=False)  # Quantity in THIS delivery

    # === NOTES ===
    notes = Column(Text, nullable=True)

    # === RELATIONSHIPS ===
    delivery = relationship("SalesDelivery", backref="items")
    sales_order_item = relationship("SalesOrderItem", backref="delivery_items")
    item = relationship("Item", backref="sales_delivery_items")
    workspace = relationship("Workspace", backref="sales_delivery_items")
