"""Miscellaneous project cost model"""
from sqlalchemy import Column, Integer, String, Numeric, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base_class import Base


class MiscellaneousProjectCost(Base):
    """Miscellaneous project cost model"""

    __tablename__ = "miscellaneous_project_costs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    project_component_id = Column(Integer, ForeignKey("project_components.id"), nullable=True)
    name = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    amount = Column(Numeric(15, 2), nullable=False)

    # Relationships
    project = relationship("Project", backref="miscellaneous_costs")
    project_component = relationship("ProjectComponent", backref="miscellaneous_costs")
