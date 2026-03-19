"""Project component item ledger model - tracks all project item consumption"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Numeric, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base_class import Base


class ProjectComponentItemLedger(Base):
    """
    Ledger tracking all project component item transactions.
    Immutable audit trail of item allocations and consumption for project components.
    """

    __tablename__ = "project_component_item_ledger"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    project_component_id = Column(Integer, ForeignKey("project_components.id", ondelete="RESTRICT"), nullable=False, index=True)
    item_id = Column(Integer, ForeignKey("items.id", ondelete="RESTRICT"), nullable=False, index=True)

    # === TRANSACTION DETAILS ===
    transaction_type = Column(String(50), nullable=False, index=True)
    # Valid values: 'purchase_order', 'manual_add', 'transfer_in', 'transfer_out',
    #               'consumption', 'damaged', 'inventory_adjustment', 'cost_adjustment'

    quantity = Column(Integer, nullable=False)
    # Always positive, direction determined by transaction_type
    # For cost_adjustment, quantity = 0

    # === COST TRACKING ===
    unit_cost = Column(Numeric(15, 2), nullable=False)  # Cost per unit at time of transaction
    total_cost = Column(Numeric(15, 2), nullable=False)  # unit_cost * quantity
    # NOTE: For cost_adjustment transactions, unit_cost represents the new/corrected cost

    # === STATE TRACKING (for reconciliation) ===
    qty_before = Column(Integer, nullable=False)  # Quantity before this transaction
    qty_after = Column(Integer, nullable=False)   # Quantity after (calculated based on transaction_type)
    value_before = Column(Numeric(15, 2), nullable=True)  # Total value before transaction
    value_after = Column(Numeric(15, 2), nullable=True)   # Total value after transaction

    # TODO: Implement avg_price calculation strategy
    # Options: FIFO, LIFO, Weighted Average, Moving Average
    # Current: Store before/after values, calculate avg on-the-fly in DAO
    avg_price_before = Column(Numeric(15, 2), nullable=True)  # Average price before transaction
    avg_price_after = Column(Numeric(15, 2), nullable=True)   # Average price after transaction

    # === ATTRIBUTION (polymorphic source) ===
    source_type = Column(String(50), nullable=False, index=True)
    # Valid values: 'order', 'manual', 'adjustment', 'transfer', 'project_allocation'
    source_id = Column(Integer, nullable=True)  # Generic pointer to source entity

    # Denormalized FKs for easy querying
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="SET NULL"), nullable=True, index=True)
    invoice_id = Column(Integer, ForeignKey("account_invoices.id", ondelete="SET NULL"), nullable=True, index=True)

    # === TRANSFER CONTEXT ===
    # For transfer_in - where items came from (usually storage via STP order)
    transfer_source_type = Column(String(50), nullable=True)  # 'storage', 'external'
    transfer_source_id = Column(Integer, nullable=True)  # factory_id, etc.
    # For transfer_out - if items are returned
    transfer_destination_type = Column(String(50), nullable=True)  # 'storage', 'damaged'
    transfer_destination_id = Column(Integer, nullable=True)  # factory_id, etc.

    # === NOTES & AUDIT ===
    notes = Column(Text, nullable=True)
    performed_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=False, index=True)
    performed_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    # === RELATIONSHIPS ===
    project_component = relationship("ProjectComponent", backref="component_ledger_entries")
    item = relationship("Item", backref="project_component_ledger_entries")
    order = relationship("Order", backref="project_component_ledger_entries")
    invoice = relationship("AccountInvoice", backref="project_component_ledger_entries")
    performer = relationship("Profile", foreign_keys=[performed_by], backref="project_component_ledger_entries")
