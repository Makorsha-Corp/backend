"""Sales order item model - line items in sales orders"""
from sqlalchemy import Column, Integer, ForeignKey, Text, Numeric, String
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class SalesOrderItem(Base):
    """
    Line items in sales orders.
    Tracks what's being sold and delivery progress.
    """

    __tablename__ = "sales_order_items"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    sales_order_id = Column(Integer, ForeignKey("sales_orders.id", ondelete="CASCADE"), nullable=False, index=True)
    item_id = Column(Integer, ForeignKey("items.id", ondelete="RESTRICT"), nullable=False, index=True)

    # === QUANTITY ===
    quantity_ordered = Column(Integer, nullable=False)  # Total quantity in contract
    quantity_delivered = Column(Integer, nullable=False, default=0)  # How much delivered so far
    # quantity_remaining = quantity_ordered - quantity_delivered (calculated)

    # === PRICING ===
    unit_price = Column(Numeric(15, 2), nullable=False)  # Selling price per unit
    line_total = Column(Numeric(15, 2), nullable=False)  # quantity_ordered * unit_price

    # === NOTES ===
    notes = Column(Text, nullable=True)

    # === RELATIONSHIPS ===
    sales_order = relationship("SalesOrder", backref="items")
    item = relationship("Item", backref="sales_order_items", lazy="joined")

    @property
    def item_name(self) -> str | None:
        return self.item.name if self.item else None

    @property
    def item_unit(self) -> str | None:
        return self.item.unit if self.item else None

    @property
    def quantity_remaining(self) -> int:
        return max(0, self.quantity_ordered - self.quantity_delivered)

    workspace = relationship("Workspace", backref="sales_order_items")
