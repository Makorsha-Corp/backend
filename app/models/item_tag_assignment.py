"""Item tag assignment model"""
from sqlalchemy import Column, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base_class import Base


class ItemTagAssignment(Base):
    """Junction table linking items to tags (many-to-many)"""

    __tablename__ = "item_tag_assignments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    item_id = Column(Integer, ForeignKey("items.id", ondelete="CASCADE"), nullable=False, index=True)
    tag_id = Column(Integer, ForeignKey("item_tags.id", ondelete="CASCADE"), nullable=False, index=True)

    assigned_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    assigned_by = Column(Integer, ForeignKey("profiles.id"), nullable=True)

    # Relationships
    item = relationship("Item", backref="tag_assignments")
    tag = relationship("ItemTag", backref="item_assignments")
    assigner = relationship("Profile", foreign_keys=[assigned_by], backref="item_tag_assignments")

    # Constraints
    __table_args__ = (
        UniqueConstraint('item_id', 'tag_id', name='uq_item_tag'),
    )
