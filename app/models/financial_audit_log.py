"""Financial audit log model - comprehensive tracking of all financial operations"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base


class FinancialAuditLog(Base):
    """
    Comprehensive audit log for all financial operations.

    Tracks all changes to accounts, invoices, and payments for complete audit trail.
    """

    __tablename__ = "financial_audit_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)

    # What entity was changed
    entity_type = Column(String(50), nullable=False, index=True)  # 'account', 'invoice', 'payment'
    entity_id = Column(Integer, nullable=False, index=True)

    # What happened
    action_type = Column(String(50), nullable=False, index=True)
    # 'created', 'updated', 'deleted', 'restored', 'status_changed', 'payment_added', 'payment_removed'

    # Related entity (e.g., payment links to invoice, invoice links to account)
    related_entity_type = Column(String(50), nullable=True)
    related_entity_id = Column(Integer, nullable=True, index=True)

    # Change details (JSON for flexibility)
    changes = Column(JSON, nullable=True)  # {"before": {...}, "after": {...}}

    # Metadata
    description = Column(Text, nullable=True)  # Human-readable description
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(255), nullable=True)

    # Who and when
    performed_by = Column(Integer, ForeignKey("profiles.id"), nullable=False)
    performed_at = Column(DateTime, nullable=False, server_default=func.now(), index=True)

    # Relationships
    user = relationship("Profile", foreign_keys=[performed_by], backref="financial_audit_logs")
