"""Invoice payment model - tracks individual payment transactions"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Numeric, Date
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base


class InvoicePayment(Base):
    """Invoice payment model - individual payment transactions for invoices"""

    __tablename__ = "invoice_payments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    invoice_id = Column(Integer, ForeignKey("account_invoices.id", ondelete="CASCADE"), nullable=False, index=True)

    # Payment Details
    payment_amount = Column(Numeric(15, 2), nullable=False)
    payment_date = Column(Date, nullable=False, index=True)
    payment_method = Column(String(50), nullable=True)  # 'cash', 'bank_transfer', 'cheque', 'card'
    payment_reference = Column(String(100), nullable=True)  # Cheque number, transaction ID, etc.

    # Bank Details
    bank_name = Column(String(255), nullable=True)
    transaction_id = Column(String(100), nullable=True)

    # Notes
    notes = Column(Text, nullable=True)

    # Audit
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    created_by = Column(Integer, ForeignKey("profiles.id"), nullable=True)

    # Relationships
    invoice = relationship("AccountInvoice", backref="payments")
    creator = relationship("Profile", foreign_keys=[created_by], backref="invoice_payments")
