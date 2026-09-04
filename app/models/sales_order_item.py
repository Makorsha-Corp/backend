"""Sales order item model - line items in sales orders"""
from decimal import Decimal
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
    quantity_ordered = Column(Numeric(15, 2), nullable=False)  # Total quantity in contract
    quantity_delivered = Column(Numeric(15, 2), nullable=False, default=0)  # How much delivered/fulfilled so far
    quantity_returned = Column(Numeric(15, 2), nullable=False, default=0, server_default='0')
    quantity_refunded = Column(Numeric(15, 2), nullable=False, default=0, server_default='0')
    # Bumped only by 'refund'-type return completions; counts toward the fully-delivered
    # check alongside quantity_delivered so a refunded quantity doesn't need redelivering.
    # quantity_remaining = quantity_ordered - quantity_delivered - quantity_refunded (calculated)

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
    def quantity_remaining(self) -> Decimal:
        """How much is still expected to be delivered (refunded quantity no longer counts)."""
        remaining = (
            Decimal(str(self.quantity_ordered or 0))
            - Decimal(str(self.quantity_delivered or 0))
            - Decimal(str(self.quantity_refunded or 0))
        )
        return max(Decimal('0'), remaining)

    @property
    def quantity_planned(self) -> Decimal:
        """Quantity committed to deliveries that are planned but not yet completed or cancelled."""
        return sum(
            (
                Decimal(str(di.quantity_delivered))
                for di in self.delivery_items
                if di.delivery is not None and di.delivery.delivery_status == "planned"
            ),
            Decimal('0'),
        )

    @property
    def quantity_available_to_plan(self) -> Decimal:
        """How much of this line can still be added to a NEW delivery plan."""
        available = (
            Decimal(str(self.quantity_ordered or 0))
            - Decimal(str(self.quantity_delivered or 0))
            - Decimal(str(self.quantity_refunded or 0))
            - self.quantity_planned
        )
        return max(Decimal('0'), available)

    @property
    def quantity_pending_returned(self) -> Decimal:
        """Quantity reserved by returns that are started but not yet completed."""
        return sum(
            (Decimal(str(ri.quantity_returned)) for ri in self.return_items if ri.return_.status == 'pending'),
            Decimal('0'),
        )

    @property
    def quantity_available_to_return(self) -> Decimal:
        """How much of this line can still be returned."""
        remaining = (
            Decimal(str(self.quantity_delivered or 0))
            - Decimal(str(self.quantity_returned or 0))
            - self.quantity_pending_returned
        )
        return max(Decimal('0'), remaining)

    workspace = relationship("Workspace", backref="sales_order_items")
