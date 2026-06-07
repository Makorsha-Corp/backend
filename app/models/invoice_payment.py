"""Invoice payment model - tracks individual payment transactions"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text, Numeric, Date
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base


class InvoicePayment(Base):
    """Invoice payment model - individual payment transactions for invoices.

    Payments can be voided individually. Voided payments are excluded from
    invoice paid_amount calculations.
    """

    __tablename__ = "invoice_payments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    invoice_id = Column(Integer, ForeignKey("account_invoices.id", ondelete="CASCADE"), nullable=False, index=True)

    # Payment Details
    payment_amount = Column(Numeric(15, 2), nullable=False)
    payment_date = Column(Date, nullable=False, index=True)
    payment_method = Column(String(50), nullable=True)  # 'cash', 'bank_transfer', 'cheque', 'card'
    payment_reference = Column(String(100), nullable=True)

    # Bank Details
    bank_name = Column(String(255), nullable=True)
    transaction_id = Column(String(100), nullable=True)

    # Notes
    notes = Column(Text, nullable=True)

    # Void
    is_voided = Column(Boolean, nullable=False, default=False)
    voided_at = Column(DateTime, nullable=True)
    voided_by = Column(Integer, ForeignKey("profiles.id"), nullable=True)
    void_note = Column(Text, nullable=True)

    # Audit
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    created_by = Column(Integer, ForeignKey("profiles.id"), nullable=True)

    # Relationships
    invoice = relationship("AccountInvoice", backref="payments")
    creator = relationship("Profile", foreign_keys=[created_by], backref="invoice_payments")
    voider = relationship("Profile", foreign_keys=[voided_by], backref="voided_payments")
