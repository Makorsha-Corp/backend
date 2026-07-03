"""Invoice event model — append-only activity log for an invoice."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship, backref
from app.db.base_class import Base


class InvoiceEvent(Base):
    """
    Append-only event log for an invoice. Replaces invoice_status_tracker and
    financial_audit_logs for all invoice-related activity.

    event_type values:
        created, confirmed, reverted_to_draft, voided,
        items_synced, item_manually_updated,
        payment_recorded, payment_voided,
        receiving_started_set, allow_payments_changed, payment_lock_changed,
        due_date_changed
    """

    __tablename__ = "invoice_events"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    invoice_id = Column(Integer, ForeignKey("account_invoices.id", ondelete="CASCADE"), nullable=False, index=True)

    event_type = Column(String(50), nullable=False)
    description = Column(Text, nullable=False)
    metadata_json = Column("metadata_json", JSON, nullable=True)

    performed_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    invoice = relationship("AccountInvoice", backref=backref("events", passive_deletes=True))
    performer = relationship("Profile", foreign_keys=[performed_by])
