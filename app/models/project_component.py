"""Project component model"""
from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey, Text, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base_class import Base
from app.models.enums import ProjectStatusEnum


class ProjectComponent(Base):
    """Project component model"""

    __tablename__ = "project_components"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    budget = Column(Numeric(15, 2), nullable=True)
    deadline = Column(DateTime, nullable=True)
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    status = Column(Enum(ProjectStatusEnum), nullable=False, default=ProjectStatusEnum.PLANNING)

    # Relationships
    project = relationship("Project", backref="components")
