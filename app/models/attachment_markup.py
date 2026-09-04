"""Per-user vector markup layers for attachments."""
from sqlalchemy import Column, Integer, DateTime, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base_class import Base


class AttachmentMarkup(Base):
    """One markup layer per user per attachment (overlay JSON, not file bytes)."""

    __tablename__ = "attachment_markups"
    __table_args__ = (
        UniqueConstraint("attachment_id", "user_id", name="uq_attachment_markup_user"),
    )

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
    payload = Column(JSON, nullable=False)
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    attachment = relationship("Attachment", backref="markups")
    user = relationship("Profile")
