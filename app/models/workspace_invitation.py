"""WorkspaceInvitation model"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.db.base_class import Base


class WorkspaceInvitation(Base):
    """Workspace invitation model - pending workspace invitations"""

    __tablename__ = "workspace_invitations"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    workspace_id = Column(Integer, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True)
    email = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False)
    position = Column(String(255), nullable=True)

    # Invitation details
    invited_by_user_id = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)
    token = Column(String(255), unique=True, nullable=False, index=True)

    # Status
    status = Column(String(50), nullable=False, default='pending', index=True)  # 'pending', 'accepted', 'expired', 'cancelled'

    # Timestamps
    invited_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    accepted_at = Column(DateTime, nullable=True)
    accepted_by_user_id = Column(Integer, ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True)

    # Relationships
    workspace = relationship("Workspace", back_populates="invitations")
    invited_by = relationship("Profile", foreign_keys=[invited_by_user_id], backref="sent_workspace_invitations")
    accepted_by = relationship("Profile", foreign_keys=[accepted_by_user_id])
