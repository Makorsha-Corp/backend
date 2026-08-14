"""Sales order model - contracts with customers for selling goods"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Numeric, Date, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime, date
from app.db.base_class import Base
from app.utils.time import utcnow


class SalesOrder(Base):
    """
    Sales orders (contracts) with customers.
    Can have multiple deliveries over time.
    Linked to clients (accounts) and results in receivable invoices.
    """

    __tablename__ = "sales_orders"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)

    # === REFERENCE ===
    sales_order_number = Column(String(100), nullable=False, unique=True, index=True)
    # Auto-generated: SO-2025-001

    # === CUSTOMER (ACCOUNT) ===
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False, index=True)
    # Required - which customer we're selling to (must have 'client' tag)

    # === ORIGIN ===
    factory_id = Column(Integer, ForeignKey("factories.id", ondelete="RESTRICT"), nullable=False, index=True)
    # Which factory is fulfilling this order

    # === DATES ===
    order_date = Column(Date, nullable=False, default=date.today)
    expected_delivery_date = Column(Date, nullable=True)

    # === TOTALS (calculated from line items) ===
    total_amount = Column(Numeric(15, 2), nullable=False, default=0)

    # === WORKFLOW ===
    current_status_id = Column(Integer, ForeignKey("statuses.id", ondelete="RESTRICT"), nullable=False, index=True)

    # === DELIVERY TRACKING ===
    is_fully_delivered = Column(Boolean, nullable=False, default=False)

    # === INVOICE LINKAGE ===
    invoice_id = Column(Integer, ForeignKey("account_invoices.id", ondelete="SET NULL"), nullable=True, index=True)
    is_invoiced = Column(Boolean, nullable=False, default=False)
    paid = Column(Boolean, nullable=False, default=False)

    # === APPROVAL WORKFLOW ===
    # current_status_id above is retained at the DB level (NOT NULL/FK) but is no
    # longer read or written by the sales flow — lifecycle now runs entirely on
    # these dedicated columns instead of the generic Status table.
    customer_confirmed = Column(Boolean, nullable=False, default=False)
    details_confirmed = Column(Boolean, nullable=False, default=False)
    items_confirmed = Column(Boolean, nullable=False, default=False)
    invoice_confirmed = Column(Boolean, nullable=False, default=False)
    required_approvals = Column(Integer, nullable=True)  # null = all assigned approvers required

    # === COMPLETION ===
    order_completed = Column(Boolean, nullable=False, default=False)
    completed_at = Column(DateTime, nullable=True)
    completed_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)

    # === DESCRIPTION ===
    description = Column(Text, nullable=True)

    # === AUDIT ===
    created_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime, nullable=True, onupdate=utcnow)
    items_updated_at = Column(DateTime, nullable=True)

    # === RELATIONSHIPS ===
    account = relationship("Account", backref="sales_orders")
    factory = relationship("Factory", backref="sales_orders")
    current_status = relationship("Status", backref="sales_orders")
    invoice = relationship("AccountInvoice", backref="sales_orders")
    creator = relationship("Profile", foreign_keys=[created_by], backref="created_sales_orders")
    updater = relationship("Profile", foreign_keys=[updated_by], backref="updated_sales_orders")
    completer = relationship("Profile", foreign_keys=[completed_by], backref="completed_sales_orders")
    approvers = relationship("SalesOrderApprover", back_populates="sales_order", cascade="all, delete-orphan")
    workspace = relationship("Workspace", backref="sales_orders")
