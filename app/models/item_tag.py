"""Item tag model"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base_class import Base


class ItemTag(Base):
    """Item tag model for categorizing items"""

    __tablename__ = "item_tags"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)  # Display name: "Raw Material", "Machine Part"
    tag_code = Column(String, nullable=False)  # Internal identifier: "raw_material", "machine_part"
    color = Column(String(7), nullable=True)  # Hex color for UI: "#3B82F6"
    icon = Column(String(50), nullable=True)  # Icon name: "package", "gear", "beaker"
    description = Column(Text, nullable=True)  # Helpful description for users

    # System management
    is_system_tag = Column(Boolean, nullable=False, default=False)  # Can't be deleted/renamed
    is_active = Column(Boolean, nullable=False, default=True)  # Soft delete
    usage_count = Column(Integer, nullable=False, default=0)  # Number of items with this tag

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_by = Column(Integer, ForeignKey("profiles.id"), nullable=True)

    # Relationships
    creator = relationship("Profile", foreign_keys=[created_by], backref="created_item_tags")
