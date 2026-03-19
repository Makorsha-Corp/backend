"""Project component task model"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base_class import Base
from app.models.enums import TaskPriorityEnum


class ProjectComponentTask(Base):
    """Project component task model"""

    __tablename__ = "project_component_tasks"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    project_component_id = Column(Integer, ForeignKey("project_components.id"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    is_completed = Column(Boolean, nullable=False, default=False)
    is_note = Column(Boolean, nullable=False, default=False)
    task_priority = Column(Enum(TaskPriorityEnum), nullable=True)

    # Relationships
    project_component = relationship("ProjectComponent", backref="tasks")
