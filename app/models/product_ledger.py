"""Product ledger model - tracks all finished goods movements"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Numeric
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base


class ProductLedger(Base):
    """
    Ledger tracking all product (finished goods) transactions.
    Immutable audit trail - only notes can be updated.
    """

    __tablename__ = "product_ledger"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    factory_id = Column(Integer, ForeignKey("factories.id", ondelete="RESTRICT"), nullable=False, index=True)
    item_id = Column(Integer, ForeignKey("items.id", ondelete="RESTRICT"), nullable=False, index=True)

    # Transaction details
    transaction_type = Column(String(50), nullable=False, index=True)
    quantity = Column(Integer, nullable=False)

    # Cost tracking
    unit_cost = Column(Numeric(15, 2), nullable=True)
    total_cost = Column(Numeric(15, 2), nullable=True)

    # State tracking (for reconciliation)
    qty_before = Column(Integer, nullable=False)
    qty_after = Column(Integer, nullable=False)
    avg_cost_before = Column(Numeric(15, 2), nullable=True)
    avg_cost_after = Column(Numeric(15, 2), nullable=True)

    # Attribution
    source_type = Column(String(50), nullable=True, index=True)
    source_id = Column(Integer, nullable=True)

    # Transfer context
    transfer_source_type = Column(String(50), nullable=True)
    transfer_source_id = Column(Integer, nullable=True)
    transfer_destination_type = Column(String(50), nullable=True)
    transfer_destination_id = Column(Integer, nullable=True)

    # Notes & audit
    notes = Column(Text, nullable=True)
    performed_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True, index=True)
    performed_at = Column(DateTime, nullable=False, server_default=func.now(), index=True)

    # Relationships
    factory = relationship("Factory", backref="product_ledger_entries")
    item = relationship("Item", backref="product_ledger_entries")
    performer = relationship("Profile", foreign_keys=[performed_by], backref="product_ledger_entries")
