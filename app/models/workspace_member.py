"""WorkspaceMember model"""
from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base_class import Base


class WorkspaceMember(Base):
    """Workspace member model - user-workspace membership with role"""

    __tablename__ = "workspace_members"
    __table_args__ = (
        UniqueConstraint('workspace_id', 'user_id', name='uq_workspace_user'),
    )

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True)

    # Role assignment
    role = Column(String(50), nullable=False)  # 'owner', 'finance', 'ground-team', 'ground-team-manager'

    # Invitation tracking
    invited_by_user_id = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    invited_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    joined_at = Column(DateTime, nullable=True)

    # Status
    status = Column(String(50), nullable=False, default='active')  # 'active', 'suspended', 'invited'

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    workspace = relationship("Workspace", back_populates="members")
    user = relationship("Profile", foreign_keys=[user_id], backref="workspace_memberships")
    invited_by = relationship("Profile", foreign_keys=[invited_by_user_id])
