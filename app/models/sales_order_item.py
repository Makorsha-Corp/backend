"""Sales order item model - line items in sales orders"""
from sqlalchemy import Column, Integer, ForeignKey, Text, Numeric, String, CheckConstraint, Boolean
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class SalesOrderItem(Base):
    """
    Line items in sales orders.
    Tracks what's being sold and delivery progress.

    A line either references a catalog Item (item_id set, typically sourced from a
    sellable Product) or is a free-text line (description set, item_id null) — e.g.
    "Installation fee". Whether a line needs physical delivery is decided per-line
    by the user at add-time (requires_delivery), independent of the item source.
    """

    __tablename__ = "sales_order_items"
    __table_args__ = (
        CheckConstraint(
            "item_id IS NOT NULL OR description IS NOT NULL",
            name="ck_sales_order_items_item_or_description",
        ),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    sales_order_id = Column(Integer, ForeignKey("sales_orders.id", ondelete="CASCADE"), nullable=False, index=True)
    item_id = Column(Integer, ForeignKey("items.id", ondelete="RESTRICT"), nullable=True, index=True)

    # === FREE-TEXT LINE ===
    description = Column(Text, nullable=True)  # Used when item_id is null (e.g. "Installation fee")

    # === FULFILLMENT ===
    requires_delivery = Column(Boolean, nullable=False, default=True, server_default='true')
    # True: fulfilled via SalesDelivery workflow (ships, deducts Product stock).
    # False: fulfilled directly (one-click), no delivery record, no stock movement.
    # User-decided per line at add-time — independent of whether the line is a
    # catalog Product or free-text.

    # === QUANTITY ===
    quantity_ordered = Column(Integer, nullable=False)  # Total quantity in contract
    quantity_delivered = Column(Integer, nullable=False, default=0)  # How much delivered/fulfilled so far
    # quantity_remaining = quantity_ordered - quantity_delivered (calculated)

    # === PRICING ===
    unit_price = Column(Numeric(15, 2), nullable=False)  # Selling price per unit
    line_total = Column(Numeric(15, 2), nullable=False)  # quantity_ordered * unit_price

    # === NOTES ===
    notes = Column(Text, nullable=True)

    # === COMPLETION ===
    fulfillment_completion_code = Column(String(100), nullable=True)

    # === RELATIONSHIPS ===
    sales_order = relationship("SalesOrder", backref="items")
    item = relationship("Item", backref="sales_order_items", lazy="joined")

    @property
    def item_name(self) -> str | None:
        return self.item.name if self.item else self.description

    @property
    def item_unit(self) -> str | None:
        return self.item.unit if self.item else None

    @property
    def item_type(self) -> str:
        """'physical' | 'service' — free-text lines are always service-like."""
        return self.item.item_type if self.item else "service"

    @property
    def quantity_remaining(self) -> int:
        return max(0, self.quantity_ordered - self.quantity_delivered)

    @property
    def quantity_planned(self) -> int:
        """Quantity committed to deliveries that are planned but not yet completed or cancelled."""
        return sum(
            di.quantity_delivered
            for di in self.delivery_items
            if di.delivery is not None and di.delivery.delivery_status == "planned"
        )

    @property
    def quantity_available_to_plan(self) -> int:
        """How much of this line can still be added to a NEW delivery plan."""
        return max(0, self.quantity_ordered - self.quantity_delivered - self.quantity_planned)

    workspace = relationship("Workspace", backref="sales_order_items")
