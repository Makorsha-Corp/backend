"""Account invoice model - financial layer for tracking payables and receivables"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text, Numeric, Date
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base


class AccountInvoice(Base):
    """
    Account invoice model - represents bills/invoices with accounts.
    Can be payable (you owe them) or receivable (they owe you).
    """

    __tablename__ = "account_invoices"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="SET NULL"), nullable=True, index=True)

    # Invoice Type
    invoice_type = Column(String(20), nullable=False, index=True)  # 'payable' or 'receivable'

    # Amounts
    invoice_amount = Column(Numeric(15, 2), nullable=False)  # Original amount invoiced
    paid_amount = Column(Numeric(15, 2), nullable=False, default=0)  # Amount paid so far
    # outstanding_amount is CALCULATED: (invoice_amount - paid_amount)

    # Reference Numbers
    invoice_number = Column(String(100), nullable=True)  # Your internal invoice number
    vendor_invoice_number = Column(String(100), nullable=True)  # Their invoice number (if payable)

    # Dates
    invoice_date = Column(Date, nullable=False)
    due_date = Column(Date, nullable=True)

    # Status
    payment_status = Column(String(20), nullable=False, default='unpaid', index=True)  # 'unpaid', 'partial', 'paid', 'overdue'

    # Admin Controls
    allow_payments = Column(Boolean, nullable=False, default=True)  # Admin can lock payments
    payment_locked_reason = Column(Text, nullable=True)  # Why payments are locked

    # Description
    description = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    # Audit
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    created_by = Column(Integer, ForeignKey("profiles.id"), nullable=True)
    updated_at = Column(DateTime, nullable=True, onupdate=func.now())
    updated_by = Column(Integer, ForeignKey("profiles.id"), nullable=True)

    # Relationships
    account = relationship("Account", backref="invoices")
    order = relationship("Order", backref="invoices")
    creator = relationship("Profile", foreign_keys=[created_by], backref="created_invoices")
    updater = relationship("Profile", foreign_keys=[updated_by], backref="updated_invoices")
