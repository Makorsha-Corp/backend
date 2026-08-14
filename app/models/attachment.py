"""Attachment model"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text, BigInteger
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class Attachment(Base):
    """Attachment model for file uploads (Cloudinary-backed metadata)."""

    __tablename__ = "attachments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    file_url = Column(String, nullable=True)
    file_name = Column(String, nullable=False)
    mime_type = Column(String, nullable=False)
    file_size = Column(BigInteger, nullable=False)
    uploaded_by = Column(Integer, ForeignKey("profiles.id"), nullable=False)
    uploaded_at = Column(DateTime, nullable=False, server_default=func.now())
    note = Column(Text, nullable=True)
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by = Column(Integer, ForeignKey("profiles.id"), nullable=True)

    storage_provider = Column(String(32), nullable=False, default="cloudinary")
    public_id = Column(String(512), nullable=True, index=True)
    asset_folder = Column(String(512), nullable=True)
    resource_type = Column(String(16), nullable=False, default="image")
    delivery_type = Column(String(16), nullable=False, default="upload")
    format = Column(String(16), nullable=True)
    version = Column(BigInteger, nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    page_count = Column(Integer, nullable=True)
    asset_id = Column(String(64), nullable=True)
    etag = Column(String(64), nullable=True)
    upload_status = Column(String(16), nullable=False, default="pending", index=True)

    uploader = relationship("Profile", foreign_keys=[uploaded_by], backref="uploaded_attachments")
    deleter = relationship("Profile", foreign_keys=[deleted_by], backref="deleted_attachments")
    links = relationship("AttachmentLink", back_populates="attachment", cascade="all, delete-orphan")
