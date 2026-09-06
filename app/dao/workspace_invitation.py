"""WorkspaceInvitation DAO"""
from typing import Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
from app.dao.base import BaseDAO
from app.models.workspace_invitation import WorkspaceInvitation
from app.schemas.workspace_invitation import WorkspaceInvitationCreate
from app.utils.time import utcnow


class WorkspaceInvitationDAO(BaseDAO[WorkspaceInvitation, WorkspaceInvitationCreate, dict]):
    """DAO for workspace invitation operations"""

    def get_by_token(self, db: Session, *, token: str) -> Optional[WorkspaceInvitation]:
        """Get invitation by token"""
        return db.query(WorkspaceInvitation).filter(WorkspaceInvitation.token == token).first()

    def get_pending_invitations(
        self, db: Session, *, workspace_id: int
    ) -> List[WorkspaceInvitation]:
        """Get all pending invitations for workspace"""
        return (
            db.query(WorkspaceInvitation)
            .filter(
                WorkspaceInvitation.workspace_id == workspace_id,
                WorkspaceInvitation.status == 'pending',
                WorkspaceInvitation.expires_at > utcnow()
            )
            .all()
        )

    def get_user_invitations(self, db: Session, *, email: str) -> List[WorkspaceInvitation]:
        """Get all pending invitations for user email"""
        return (
            db.query(WorkspaceInvitation)
            .filter(
                WorkspaceInvitation.email == email,
                WorkspaceInvitation.status == 'pending',
                WorkspaceInvitation.expires_at > utcnow()
            )
            .all()
        )

    def count_pending_invitations(self, db: Session, *, workspace_id: int) -> int:
        """Get count of pending non-expired invitations for workspace"""
        return (
            db.query(WorkspaceInvitation)
            .filter(
                WorkspaceInvitation.workspace_id == workspace_id,
                WorkspaceInvitation.status == 'pending',
                WorkspaceInvitation.expires_at > utcnow()
            )
            .count()
        )

    def get_all_invitations(
        self, db: Session, *, workspace_id: int
    ) -> List[WorkspaceInvitation]:
        """Get all invitations for workspace regardless of status"""
        return (
            db.query(WorkspaceInvitation)
            .filter(WorkspaceInvitation.workspace_id == workspace_id)
            .all()
        )

workspace_invitation_dao = WorkspaceInvitationDAO(WorkspaceInvitation)
