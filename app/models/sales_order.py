"""Sales order model - contracts with customers for selling goods"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Numeric, Date, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime, date
from app.db.base_class import Base


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
    quotation_sent_date = Column(Date, nullable=True)
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

    # === NOTES ===
    notes = Column(Text, nullable=True)

    # === AUDIT ===
    created_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime, nullable=True, onupdate=datetime.utcnow)

    # === RELATIONSHIPS ===
    account = relationship("Account", backref="sales_orders")
    factory = relationship("Factory", backref="sales_orders")
    current_status = relationship("Status", backref="sales_orders")
    invoice = relationship("AccountInvoice", backref="sales_orders")
    creator = relationship("Profile", foreign_keys=[created_by], backref="created_sales_orders")
    updater = relationship("Profile", foreign_keys=[updated_by], backref="updated_sales_orders")
    workspace = relationship("Workspace", backref="sales_orders")
