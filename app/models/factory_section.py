"""Factory section model"""
from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base


class FactorySection(Base):
    """Factory section model"""

    __tablename__ = "factory_sections"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    factory_id = Column(Integer, ForeignKey("factories.id"), nullable=False)

    # Audit fields
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    created_by = Column(Integer, ForeignKey("profiles.id"), nullable=True)
    updated_at = Column(DateTime, nullable=True, onupdate=func.now())
    updated_by = Column(Integer, ForeignKey("profiles.id"), nullable=True)

    # Status
    is_active = Column(Boolean, nullable=False, default=True)
    is_deleted = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime, nullable=True)
    deleted_by = Column(Integer, ForeignKey("profiles.id"), nullable=True)

    # Relationships
    factory = relationship("Factory", backref="sections")
    creator = relationship("Profile", foreign_keys=[created_by], backref="created_factory_sections")
    updater = relationship("Profile", foreign_keys=[updated_by], backref="updated_factory_sections")
    deleter = relationship("Profile", foreign_keys=[deleted_by], backref="deleted_factory_sections")
