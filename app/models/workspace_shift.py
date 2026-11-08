"""Workspace production shift windows (local wall-clock)."""
from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, DateTime, Time
from sqlalchemy.orm import relationship
from app.db.base_class import Base
from app.utils.time import utcnow


class WorkspaceShift(Base):
    __tablename__ = "workspace_shifts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(80), nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    sort_order = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True)

    created_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    updated_by = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)

    workspace = relationship("Workspace", backref="shifts")
