"""Invoice status tracker — append-only log of invoice lifecycle transitions"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class InvoiceStatusTracker(Base):
    """Append-only log of every invoice status transition.

    Written on: draft→confirmed, confirmed→draft (edit revert), confirmed→voided.
    Query this table to see the full history of an invoice's lifecycle.
    """

    __tablename__ = "invoice_status_tracker"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    invoice_id = Column(Integer, ForeignKey("account_invoices.id", ondelete="CASCADE"), nullable=False, index=True)

    from_status = Column(String(20), nullable=False)
    to_status = Column(String(20), nullable=False)

    changed_by = Column(Integer, ForeignKey("profiles.id"), nullable=True)
    changed_at = Column(DateTime, nullable=False)

    # Relationships
    invoice = relationship("AccountInvoice", backref="status_history")
    changer = relationship("Profile", foreign_keys=[changed_by])
