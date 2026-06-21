"""Universal notification model."""
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base


class Notification(Base):
    __tablename__ = "notifications"

    id           = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)

    recipient_user_id = Column(Integer, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_user_id     = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)

    # "mention" to start; extend later (approval_request, status_change, etc.)
    notification_type = Column(String(30), nullable=False, index=True, default="mention")

    # The entity the notification is about (see NotificationEntityType)
    entity_type = Column(String(30), nullable=False, index=True)
    entity_id   = Column(Integer, nullable=False)

    # The specific record that triggered it (e.g. the Discussion row)
    source_type = Column(String(30), nullable=False)   # "discussion"
    source_id   = Column(Integer, nullable=False)

    preview = Column(Text, nullable=True)   # first ~200 chars of the message

    is_read = Column(Boolean, nullable=False, default=False)
    read_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, nullable=False, server_default=func.now())

    # Relationships
    recipient = relationship("Profile", foreign_keys=[recipient_user_id], backref="notifications")
    actor     = relationship("Profile", foreign_keys=[actor_user_id])

    __table_args__ = (
        Index("ix_notifications_recipient_unread", "workspace_id", "recipient_user_id", "is_read"),
    )
