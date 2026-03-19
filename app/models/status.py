"""Status model"""
from sqlalchemy import Column, Integer, String, ForeignKey
from app.db.base_class import Base


class Status(Base):
    """Status model"""

    __tablename__ = "statuses"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    comment = Column(String, nullable=False)
