"""Item model (renamed from Part)"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from datetime import datetime
from app.db.base_class import Base


class Item(Base):
    """Item model - represents materials, parts, supplies, etc."""

    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True, onupdate=datetime.utcnow)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    unit = Column(String, nullable=False)  # kg, pcs, ltr, meter, etc.
    sku = Column(String, nullable=True)  # Stock keeping unit / part number
    created_by = Column(Integer, ForeignKey("profiles.id"), nullable=True)
    updated_by = Column(Integer, ForeignKey("profiles.id"), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
