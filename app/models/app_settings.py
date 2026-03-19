"""App settings model"""
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from app.db.base_class import Base


class AppSettings(Base):
    """App settings model"""

    __tablename__ = "app_settings"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    enabled = Column(Boolean, nullable=False, default=False)
