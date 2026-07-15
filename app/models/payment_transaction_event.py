"""Payment transaction event model — append-only audit trail for a payment transaction.

event_type values:
    initiated, redirect_success, redirect_fail, redirect_cancel, ipn_received,
    validated_success, validated_failed, risk_hold, risk_resolved, expired,
    duplicate_ignored
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship, backref
from app.db.base_class import Base


class PaymentTransactionEvent(Base):
    __tablename__ = "payment_transaction_events"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    payment_transaction_id = Column(
        Integer, ForeignKey("payment_transactions.id", ondelete="CASCADE"), nullable=False, index=True
    )

    event_type = Column(String(50), nullable=False)
    description = Column(Text, nullable=False)
    metadata_json = Column("metadata_json", JSON, nullable=True)

    performed_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    payment_transaction = relationship(
        "PaymentTransaction", backref=backref("events", passive_deletes=True, order_by="PaymentTransactionEvent.created_at")
    )
    performer = relationship("Profile", foreign_keys=[performed_by])
