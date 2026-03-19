"""Project component attachment junction model"""
from sqlalchemy import Column, Integer, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base


class ProjectComponentAttachment(Base):
    """Junction table linking project components to attachments"""

    __tablename__ = "project_component_attachments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    project_component_id = Column(Integer, ForeignKey("project_components.id", ondelete="CASCADE"), nullable=False, index=True)
    attachment_id = Column(Integer, ForeignKey("attachments.id", ondelete="CASCADE"), nullable=False, index=True)
    attached_at = Column(DateTime, nullable=False, server_default=func.now())
    attached_by = Column(Integer, ForeignKey("profiles.id"), nullable=False)

    # Relationships
    project_component = relationship("ProjectComponent", backref="attachments")
    attachment = relationship("Attachment", backref="project_component_links")
    attacher = relationship("Profile", backref="project_component_attachments")
