"""Purchase order model - for external procurement with items"""
from sqlalchemy import Column, Integer, String, DateTime, Date, ForeignKey, Text, Numeric, Boolean, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base_class import Base


class PurchaseOrder(Base):
    """
    Purchase orders for external procurement of items.
    Linked to suppliers (accounts) and results in invoices.
    """

    __tablename__ = "purchase_orders"
    __table_args__ = (
        UniqueConstraint('workspace_id', 'po_number', name='uq_po_workspace_number'),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)

    # === REFERENCE ===
    po_number = Column(String(100), nullable=False, index=True)
    # Auto-generated: PO-2025-001

    # === SUPPLIER (ACCOUNT) ===
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=True, index=True)

    # === DESTINATION ===
    destination_type = Column(String(50), nullable=False)  # 'storage', 'machine', 'project'
    destination_id = Column(Integer, nullable=False)  # factory_id, machine_id, project_component_id

    # === DATES ===
    order_date = Column(Date, nullable=True)
    expected_delivery_date = Column(Date, nullable=True)
    actual_delivery_date = Column(Date, nullable=True)  # set when order is marked complete

    # === TOTALS (calculated from line items) ===
    subtotal = Column(Numeric(15, 2), nullable=False, default=0)  # Sum of all line_subtotals
    total_amount = Column(Numeric(15, 2), nullable=False, default=0)  # Same as subtotal

    # === WORKFLOW ===
    current_status_id = Column(Integer, ForeignKey("statuses.id", ondelete="RESTRICT"), nullable=False, index=True)
    order_workflow_id = Column(Integer, ForeignKey("order_workflows.id", ondelete="RESTRICT"), nullable=True, index=True)

    # === APPROVALS ===
    required_approvals = Column(Integer, nullable=True)  # threshold; null = all assigned approvers

    # === INVOICE LINKAGE ===
    invoice_id = Column(Integer, ForeignKey("account_invoices.id", ondelete="SET NULL"), nullable=True, index=True)

    # === DESCRIPTION & NOTES ===
    description = Column(Text, nullable=True)

    # === SECTION CONFIRMS ===
    supplier_confirmed = Column(Boolean, nullable=False, default=False)
    details_confirmed = Column(Boolean, nullable=False, default=False)
    items_confirmed = Column(Boolean, nullable=False, default=False)
    invoice_confirmed = Column(Boolean, nullable=False, default=False)
    invoice_ever_linked = Column(Boolean, nullable=False, default=False, server_default='false')

    # === VOID ===
    voided = Column(Boolean, nullable=False, default=False)
    void_note = Column(Text, nullable=True)
    voided_at = Column(DateTime, nullable=True)
    voided_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)

    # === AUDIT ===
    created_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime, nullable=True, onupdate=datetime.utcnow)
    items_updated_at = Column(DateTime, nullable=True)

    # === RELATIONSHIPS ===
    account = relationship("Account", backref="purchase_orders")
    current_status = relationship("Status", backref="purchase_orders")
    workflow = relationship("OrderWorkflow", backref="purchase_orders")
    invoice = relationship("AccountInvoice", backref="purchase_orders")
    creator = relationship("Profile", foreign_keys=[created_by], backref="created_purchase_orders")
    updater = relationship("Profile", foreign_keys=[updated_by], backref="updated_purchase_orders")
    approvers = relationship(
        "PurchaseOrderApprover",
        back_populates="purchase_order",
        cascade="all, delete-orphan",
    )

    @property
    def current_status_name(self) -> str | None:
        return self.current_status.name if self.current_status else None

    @property
    def order_completed(self) -> bool:
        """True when workflow stage is Complete (set manually after full receiving)."""
        return self.current_status_name == 'Complete'
