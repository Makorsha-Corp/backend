"""WorkspaceMember DAO"""
from typing import Optional, List
from sqlalchemy.orm import Session
from app.dao.base import BaseDAO
from app.models.workspace_member import WorkspaceMember
from app.schemas.workspace_member import WorkspaceMemberCreate, WorkspaceMemberUpdate


class WorkspaceMemberDAO(BaseDAO[WorkspaceMember, WorkspaceMemberCreate, WorkspaceMemberUpdate]):
    """DAO for workspace member operations"""

    def get_by_workspace_and_user(
        self, db: Session, *, workspace_id: int, user_id: int
    ) -> Optional[WorkspaceMember]:
        """Get membership record for user in workspace"""
        return (
            db.query(WorkspaceMember)
            .filter(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user_id
            )
            .first()
        )

    def get_user_workspaces(self, db: Session, *, user_id: int) -> List[WorkspaceMember]:
        """Get all workspaces user belongs to (active only)"""
        return (
            db.query(WorkspaceMember)
            .filter(
                WorkspaceMember.user_id == user_id,
                WorkspaceMember.status == 'active'
            )
            .all()
        )

    def get_by_user(self, db: Session, *, user_id: int) -> List[WorkspaceMember]:
        """Get all workspace memberships for a user (alias for get_user_workspaces)"""
        return (
            db.query(WorkspaceMember)
            .filter(WorkspaceMember.user_id == user_id)
            .all()
        )

    def get_workspace_members(
        self, db: Session, *, workspace_id: int, status: Optional[str] = 'active'
    ) -> List[WorkspaceMember]:
        """Get all members in workspace"""
        query = db.query(WorkspaceMember).filter(WorkspaceMember.workspace_id == workspace_id)

        if status is not None:
            query = query.filter(WorkspaceMember.status == status)

        return query.all()

    def get_workspace_members_count(
        self, db: Session, *, workspace_id: int, status: str = 'active'
    ) -> int:
        """Get count of members in workspace"""
        query = db.query(WorkspaceMember).filter(WorkspaceMember.workspace_id == workspace_id)

        if status:
            query = query.filter(WorkspaceMember.status == status)

        return query.count()

    def update_role(
        self, db: Session, *, workspace_id: int, user_id: int, new_role: str, position: str | None = None
    ) -> WorkspaceMember:
        """Update user's role (and optionally position) in workspace"""
        member = self.get_by_workspace_and_user(db, workspace_id=workspace_id, user_id=user_id)
        if not member:
            raise ValueError("User is not a member of this workspace")

        member.role = new_role
        if position is not None:
            member.position = position
        db.flush()
        return member

    def get_by_workspace(self, db: Session, *, workspace_id: int) -> List[WorkspaceMember]:
        """Get all members in workspace (alias for get_workspace_members)"""
        return self.get_workspace_members(db, workspace_id=workspace_id, status=None)

    def count_active_members(self, db: Session, *, workspace_id: int) -> int:
        """Get count of active members in workspace"""
        return (
            db.query(WorkspaceMember)
            .filter(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.status == 'active'
            )
            .count()
        )

    def has_access(
        self, db: Session, *, user_id: int, workspace_id: int
    ) -> bool:
        """Check if user has access to workspace (is active member)"""
        member = self.get_by_workspace_and_user(
            db, workspace_id=workspace_id, user_id=user_id
        )
        return member is not None and member.status == 'active'


workspace_member_dao = WorkspaceMemberDAO(WorkspaceMember)
