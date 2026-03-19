"""Attachment model"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text, BigInteger
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class Attachment(Base):
    """Attachment model for file uploads"""

    __tablename__ = "attachments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    file_url = Column(String, nullable=False)
    file_name = Column(String, nullable=False)
    mime_type = Column(String, nullable=False)
    file_size = Column(BigInteger, nullable=False)  # Size in bytes
    uploaded_by = Column(Integer, ForeignKey("profiles.id"), nullable=False)
    uploaded_at = Column(DateTime, nullable=False, server_default=func.now())
    note = Column(Text, nullable=True)
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by = Column(Integer, ForeignKey("profiles.id"), nullable=True)

    # Relationships
    uploader = relationship("Profile", foreign_keys=[uploaded_by], backref="uploaded_attachments")
    deleter = relationship("Profile", foreign_keys=[deleted_by], backref="deleted_attachments")
