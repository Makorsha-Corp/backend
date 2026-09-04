"""Sales order return model - accepting delivered/fulfilled goods back from a customer"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Numeric, Boolean
from sqlalchemy.orm import relationship
from app.db.base_class import Base
from app.utils.time import utcnow


class SalesOrderReturn(Base):
    """
    A batch return of previously-delivered/fulfilled SO items back from the customer.
    Lifecycle: pending -> completed | voided.
    Starting a return immediately creates AND confirms/locks its credit-note invoice
    (invoice_type='payable' — we owe the customer) — no draft period. Completing a
    pending return restores sellable Product stock. Voiding a pending return (before
    it's completed) voids that invoice instead; nothing physical has happened yet at
    that point, so there's nothing else to reverse — the reserved quantity becomes
    available again for a new return.

    return_type decides what happens to the SO line's quantities on completion:
    'replace' only reduces quantity_delivered (quantity_ordered is untouched), reopening
    a delivery gap that must be closed with a new delivery/fulfillment before the order
    can be marked complete again. 'refund' also reduces quantity_delivered but
    additionally bumps quantity_refunded by the same amount, which counts toward the
    order-completion check so nothing further needs to be delivered for that quantity.
    """

    __tablename__ = "sales_order_returns"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    sales_order_id = Column(Integer, ForeignKey("sales_orders.id", ondelete="CASCADE"), nullable=False, index=True)

    return_number = Column(String(100), nullable=False, unique=True, index=True)
    # Auto-generated: SR-2026-001

    status = Column(String(20), nullable=False, default='pending', index=True)
    # 'pending' | 'completed' | 'voided'

    return_type = Column(String(20), nullable=False, server_default='refund')
    # 'replace' | 'refund' — chosen once for the whole return batch at start time

    invoice_id = Column(Integer, ForeignKey("account_invoices.id", ondelete="SET NULL"), nullable=True, index=True)
    paid = Column(Boolean, nullable=False, default=False)

    reason = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    completed_at = Column(DateTime, nullable=True)
    completed_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)

    created_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime, nullable=True, onupdate=utcnow)

    sales_order = relationship("SalesOrder", backref="returns")
    items = relationship("SalesOrderReturnItem", back_populates="return_", cascade="all, delete-orphan")
    creator = relationship("Profile", foreign_keys=[created_by])
    completer = relationship("Profile", foreign_keys=[completed_by])
    workspace = relationship("Workspace", backref="sales_order_returns")


class SalesOrderReturnItem(Base):
    __tablename__ = "sales_order_return_items"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    return_id = Column(Integer, ForeignKey("sales_order_returns.id", ondelete="CASCADE"), nullable=False, index=True)
    so_item_id = Column(Integer, ForeignKey("sales_order_items.id", ondelete="RESTRICT"), nullable=False, index=True)
    item_id = Column(Integer, ForeignKey("items.id", ondelete="RESTRICT"), nullable=True)
    # Nullable: free-text SO lines have no catalog item — still returnable, just skipped for inventory.

    quantity_returned = Column(Numeric(15, 2), nullable=False)
    unit_price = Column(Numeric(15, 2), nullable=True)
    notes = Column(Text, nullable=True)

    return_ = relationship("SalesOrderReturn", back_populates="items")
    so_item = relationship("SalesOrderItem", backref="return_items")
    item = relationship("Item", lazy="joined")

    @property
    def item_name(self) -> str | None:
        return self.item.name if self.item else (self.so_item.item_name if self.so_item else None)

    @property
    def item_unit(self) -> str | None:
        return self.item.unit if self.item else None
