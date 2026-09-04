"""Purchase order item model - items within a purchase order"""
from decimal import Decimal
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
    quantity_returned = Column(Numeric(15, 2), nullable=False, default=0, server_default='0')
    quantity_refunded = Column(Numeric(15, 2), nullable=False, default=0, server_default='0')
    # Bumped only by 'refund'-type return completions; counts toward the fully-received
    # check alongside quantity_received so a refunded quantity doesn't need re-receiving.
    unit_price = Column(Numeric(15, 2), nullable=True)
    line_subtotal = Column(Numeric(15, 2), nullable=True)  # quantity_ordered * unit_price when priced

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
            Decimal(str(self.quantity_received or 0))
            - Decimal(str(self.quantity_returned or 0))
            - self.quantity_pending_returned
        )
        return max(Decimal('0'), remaining)

    @property
    def quantity_remaining(self) -> Decimal:
        """How much is still expected to be received (refunded quantity no longer counts)."""
        remaining = (
            Decimal(str(self.quantity_ordered or 0))
            - Decimal(str(self.quantity_received or 0))
            - Decimal(str(self.quantity_refunded or 0))
        )
        return max(Decimal('0'), remaining)
