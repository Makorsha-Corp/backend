"""Purchase order item model - items within a purchase order"""
from sqlalchemy import Column, Integer, ForeignKey, Text, Numeric
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class PurchaseOrderItem(Base):
    """
    Individual line items within a purchase order.
    Tracks items being purchased with quantities and pricing.
    """

    __tablename__ = "purchase_order_items"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    purchase_order_id = Column(Integer, ForeignKey("purchase_orders.id", ondelete="CASCADE"), nullable=False, index=True)

    # === LINE ITEM DETAILS ===
    line_number = Column(Integer, nullable=False)

    # === ITEM ===
    item_id = Column(Integer, ForeignKey("items.id", ondelete="RESTRICT"), nullable=False, index=True)

    # === QUANTITY & PRICING ===
    quantity_ordered = Column(Numeric(15, 2), nullable=False)
    quantity_received = Column(Numeric(15, 2), nullable=False, default=0)
    unit_price = Column(Numeric(15, 2), nullable=False)
    line_subtotal = Column(Numeric(15, 2), nullable=False)  # quantity_ordered * unit_price

    # === NOTES ===
    notes = Column(Text, nullable=True)

    # === RELATIONSHIPS ===
    purchase_order = relationship("PurchaseOrder", backref="line_items")
    item = relationship("Item", backref="purchase_order_items", lazy="joined")

    @property
    def item_name(self) -> str | None:
        return self.item.name if self.item else None

    @property
    def item_unit(self) -> str | None:
        return self.item.unit if self.item else None
