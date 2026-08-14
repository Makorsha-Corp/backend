"""Polymorphic link between attachments and business entities."""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class AttachmentLink(Base):
    """Links an attachment to a workspace-scoped entity (order, project, etc.)."""

    __tablename__ = "attachment_links"
    __table_args__ = (
        UniqueConstraint("attachment_id", "entity_type", "entity_id", name="uq_attachment_link_entity"),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    attachment_id = Column(Integer, ForeignKey("attachments.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_type = Column(String(64), nullable=False)
    entity_id = Column(Integer, nullable=False)
    linked_at = Column(DateTime, nullable=False, server_default=func.now())
    linked_by = Column(Integer, ForeignKey("profiles.id"), nullable=False)

    attachment = relationship("Attachment", back_populates="links")
    linker = relationship("Profile", foreign_keys=[linked_by], backref="attachment_links")
