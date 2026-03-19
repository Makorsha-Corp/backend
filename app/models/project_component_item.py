"""Project component item model"""
from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base_class import Base


class ProjectComponentItem(Base):
    """Project component item model - items required for a project component"""

    __tablename__ = "project_component_items"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    project_component_id = Column(Integer, ForeignKey("project_components.id"), nullable=False, index=True)
    item_id = Column(Integer, ForeignKey("items.id"), nullable=False, index=True)
    qty = Column(Integer, nullable=False)

    # Relationships
    project_component = relationship("ProjectComponent", backref="items")
    item = relationship("Item", backref="project_component_items")
