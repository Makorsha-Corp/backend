"""Append-only audit log for attachment markup overlay changes."""
from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship

from app.db.base_class import Base
from app.utils.time import utcnow


class AttachmentMarkupEvent(Base):
    """Immutable markup activity for an attachment."""

    __tablename__ = "attachment_markup_events"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(
        Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    attachment_id = Column(
        Integer, ForeignKey("attachments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id = Column(
        Integer, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id = Column(String(36), nullable=True, index=True)
    event_type = Column(String(32), nullable=False)
    description = Column(Text, nullable=False)
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)

    user = relationship("Profile", foreign_keys=[user_id])
