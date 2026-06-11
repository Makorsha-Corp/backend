"""Project model"""
from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey, Text, Enum, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base_class import Base
from app.models.enums import ProjectStatusEnum, ProjectPriorityEnum, ProjectVisibilityEnum


class Project(Base):
    """Project model"""

    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    factory_id = Column(Integer, ForeignKey("factories.id"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    budget = Column(Numeric(15, 2), nullable=True)
    deadline = Column(DateTime, nullable=True)
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    priority = Column(Enum(ProjectPriorityEnum), nullable=False, default=ProjectPriorityEnum.LOW)
    status = Column(Enum(ProjectStatusEnum), nullable=False, default=ProjectStatusEnum.PLANNING)
    visibility = Column(
        String(20),
        nullable=False,
        default=ProjectVisibilityEnum.WORKSPACE.value,
        server_default=ProjectVisibilityEnum.WORKSPACE.value,
    )

    # Audit fields
    created_by = Column(Integer, ForeignKey("profiles.id"), nullable=True)
    updated_at = Column(DateTime, nullable=True, onupdate=datetime.utcnow)
    updated_by = Column(Integer, ForeignKey("profiles.id"), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by = Column(Integer, ForeignKey("profiles.id"), nullable=True)

    # Relationships
    factory = relationship("Factory", backref="projects")
    members = relationship("ProjectMember", back_populates="project", cascade="all, delete-orphan")
