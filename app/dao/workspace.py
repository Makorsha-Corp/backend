"""Workspace DAO"""
from typing import Optional
from sqlalchemy.orm import Session
from app.dao.base import BaseDAO
from app.models.workspace import Workspace
from app.schemas.workspace import WorkspaceCreate, WorkspaceUpdate


class WorkspaceDAO(BaseDAO[Workspace, WorkspaceCreate, WorkspaceUpdate]):
    """DAO for workspace operations"""

    def get_by_slug(self, db: Session, *, slug: str) -> Optional[Workspace]:
        """Get workspace by slug"""
        return db.query(Workspace).filter(Workspace.slug == slug).first()

    def get_by_owner(self, db: Session, *, owner_user_id: int) -> list[Workspace]:
        """Get all workspaces owned by user"""
        return (
            db.query(Workspace)
            .filter(Workspace.owner_user_id == owner_user_id)
            .all()
        )

    def increment_usage(
        self, db: Session, *, workspace_id: int, field: str, amount: int = 1
    ) -> Workspace:
        """
        Increment usage counter for workspace

        Args:
            workspace_id: Workspace ID
            field: Usage field to increment (e.g., 'current_members_count')
            amount: Amount to increment by (default 1)
        """
        workspace = self.get(db, id=workspace_id)
        if workspace:
            current_value = getattr(workspace, field, 0)
            setattr(workspace, field, current_value + amount)
            db.flush()
        return workspace

    def decrement_usage(
        self, db: Session, *, workspace_id: int, field: str, amount: int = 1
    ) -> Workspace:
        """
        Decrement usage counter for workspace

        Args:
            workspace_id: Workspace ID
            field: Usage field to decrement (e.g., 'current_members_count')
            amount: Amount to decrement by (default 1)
        """
        workspace = self.get(db, id=workspace_id)
        if workspace:
            current_value = getattr(workspace, field, 0)
            setattr(workspace, field, max(0, current_value - amount))
            db.flush()
        return workspace

    def check_limit(
        self, db: Session, *, workspace: Workspace, limit_field: str
    ) -> tuple[bool, int, int]:
        """
        Check if workspace has reached a limit

        Args:
            workspace: Workspace instance
            limit_field: Limit field to check (e.g., 'members', 'storage_mb')

        Returns:
            Tuple of (has_reached_limit, current_usage, max_limit)
        """
        current_field = f'current_{limit_field}_count' if not limit_field.endswith('_mb') else f'current_{limit_field}'
        max_field = f'max_{limit_field}'

        current_usage = getattr(workspace, current_field, 0)

        # Get max from subscription plan
        if workspace.subscription_plan:
            max_limit = getattr(workspace.subscription_plan, max_field, -1)
        else:
            max_limit = -1

        # -1 means unlimited
        if max_limit == -1:
            return False, current_usage, max_limit

        has_reached = current_usage >= max_limit
        return has_reached, current_usage, max_limit


workspace_dao = WorkspaceDAO(Workspace)
