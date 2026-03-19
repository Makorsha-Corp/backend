"""Access control model"""
from sqlalchemy import Column, Integer, String, Enum, ForeignKey
from app.db.base_class import Base
from app.models.enums import AccessControlTypeEnum, RoleEnum


class AccessControl(Base):
    """Access control model for RBAC"""

    __tablename__ = "access_control"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=True, index=True)
    type = Column(Enum(AccessControlTypeEnum), nullable=False)
    target = Column(String, nullable=False)
    role = Column(Enum(RoleEnum), nullable=False)
