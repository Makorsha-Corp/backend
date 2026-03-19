"""Project attachment junction model"""
from sqlalchemy import Column, Integer, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base


class ProjectAttachment(Base):
    """Junction table linking projects to attachments"""

    __tablename__ = "project_attachments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    attachment_id = Column(Integer, ForeignKey("attachments.id", ondelete="CASCADE"), nullable=False, index=True)
    attached_at = Column(DateTime, nullable=False, server_default=func.now())
    attached_by = Column(Integer, ForeignKey("profiles.id"), nullable=False)

    # Relationships
    project = relationship("Project", backref="attachments")
    attachment = relationship("Attachment", backref="project_links")
    attacher = relationship("Profile", backref="project_attachments")
