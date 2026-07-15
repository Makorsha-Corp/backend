"""Payment transaction model — the immutable ledger for SSLCommerz checkout attempts.

Deliberately generic: it only knows "collect `amount` `currency` from
`workspace_id`", not *why* the payment is happening. `value_a`..`value_d` mirror
SSLCommerz's own custom-metadata fields (echoed back unchanged by the gateway on
every callback) so a caller (e.g. future subscription-renewal logic) can stash
its own correlation data there without this table needing to know about it.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Numeric, Text, JSON
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class PaymentTransaction(Base):
    """One row per checkout attempt (one row per `tran_id`).

    status values:
        INITIATED       — session created with the gateway, awaiting outcome
        VALIDATED_SUCCESS — server-to-server validation confirmed a successful charge
        VALIDATED_FAILED  — gateway reported failure, or validation didn't match our records
        CANCELLED       — customer cancelled on the gateway's hosted page
        EXPIRED         — never resolved; reconciliation swept it after the timeout
        RISK_HOLD       — gateway flagged risk_level=1; held for admin review
    """

    __tablename__ = "payment_transactions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)

    tran_id = Column(String(30), nullable=False, unique=True, index=True)
    status = Column(String(20), nullable=False, default="INITIATED", index=True)

    amount = Column(Numeric(15, 2), nullable=False)
    currency = Column(String(3), nullable=False)

    cus_name = Column(String(255), nullable=True)
    cus_email = Column(String(255), nullable=True)
    cus_phone = Column(String(50), nullable=True)

    value_a = Column(String(255), nullable=True)
    value_b = Column(String(255), nullable=True)
    value_c = Column(String(255), nullable=True)
    value_d = Column(String(255), nullable=True)

    session_key = Column(String(64), nullable=True)
    gateway_page_url = Column(Text, nullable=True)

    val_id = Column(String(512), nullable=True, index=True)
    risk_level = Column(Integer, nullable=True)
    risk_title = Column(String(50), nullable=True)
    bank_tran_id = Column(String(100), nullable=True)
    card_type = Column(String(50), nullable=True)
    verify_sign = Column(String(255), nullable=True)

    last_ipn_payload = Column(JSON, nullable=True)

    risk_resolved_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    risk_resolved_at = Column(DateTime, nullable=True)
    risk_resolution_note = Column(Text, nullable=True)

    initiated_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    initiated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    validated_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    workspace = relationship("Workspace", backref="payment_transactions")
    initiator = relationship("Profile", foreign_keys=[initiated_by])
    risk_resolver = relationship("Profile", foreign_keys=[risk_resolved_by])
