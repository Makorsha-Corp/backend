"""Immutable audit trail for attachment lifecycle events."""
from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base_class import Base


class AttachmentLedger(Base):
    """Append-only ledger for attachment pending / ready / failed / deleted."""

    __tablename__ = "attachment_ledger"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(
        Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    attachment_id = Column(
        Integer, ForeignKey("attachments.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    transaction_type = Column(String(16), nullable=False, index=True)
    entity_type = Column(String(64), nullable=True, index=True)
    entity_id = Column(Integer, nullable=True, index=True)
    file_name = Column(String(255), nullable=False)
    mime_type = Column(String(128), nullable=False)
    file_size = Column(BigInteger, nullable=False)
    notes = Column(Text, nullable=True)
    performed_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True, index=True)
    performed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)

    attachment = relationship("Attachment", backref="ledger_entries")
    performer = relationship("Profile", foreign_keys=[performed_by], backref="attachment_ledger_entries")
