"""WorkspaceInvitation DAO"""
from typing import Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
from app.dao.base import BaseDAO
from app.models.workspace_invitation import WorkspaceInvitation
from app.schemas.workspace_invitation import WorkspaceInvitationCreate


class WorkspaceInvitationDAO(BaseDAO[WorkspaceInvitation, WorkspaceInvitationCreate, dict]):
    """DAO for workspace invitation operations"""

    def get_by_token(self, db: Session, *, token: str) -> Optional[WorkspaceInvitation]:
        """Get invitation by token"""
        return db.query(WorkspaceInvitation).filter(WorkspaceInvitation.token == token).first()

    def get_by_workspace_and_email(
        self, db: Session, *, workspace_id: int, email: str
    ) -> Optional[WorkspaceInvitation]:
        """Get invitation by workspace and email"""
        return (
            db.query(WorkspaceInvitation)
            .filter(
                WorkspaceInvitation.workspace_id == workspace_id,
                WorkspaceInvitation.email == email
            )
            .first()
        )

    def get_pending_invitations(
        self, db: Session, *, workspace_id: int
    ) -> List[WorkspaceInvitation]:
        """Get all pending invitations for workspace"""
        return (
            db.query(WorkspaceInvitation)
            .filter(
                WorkspaceInvitation.workspace_id == workspace_id,
                WorkspaceInvitation.status == 'pending',
                WorkspaceInvitation.expires_at > datetime.utcnow()
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
                WorkspaceInvitation.expires_at > datetime.utcnow()
            )
            .all()
        )

    def mark_as_accepted(
        self, db: Session, *, invitation: WorkspaceInvitation
    ) -> WorkspaceInvitation:
        """Mark invitation as accepted"""
        invitation.status = 'accepted'
        invitation.accepted_at = datetime.utcnow()
        db.flush()
        return invitation

    def mark_as_expired(
        self, db: Session, *, invitation: WorkspaceInvitation
    ) -> WorkspaceInvitation:
        """Mark invitation as expired"""
        invitation.status = 'expired'
        db.flush()
        return invitation

    def mark_as_cancelled(
        self, db: Session, *, invitation: WorkspaceInvitation
    ) -> WorkspaceInvitation:
        """Mark invitation as cancelled"""
        invitation.status = 'cancelled'
        db.flush()
        return invitation

    def cleanup_expired_invitations(self, db: Session) -> int:
        """Mark expired invitations as expired (returns count)"""
        count = (
            db.query(WorkspaceInvitation)
            .filter(
                WorkspaceInvitation.status == 'pending',
                WorkspaceInvitation.expires_at <= datetime.utcnow()
            )
            .update({'status': 'expired'})
        )
        db.flush()
        return count


workspace_invitation_dao = WorkspaceInvitationDAO(WorkspaceInvitation)
