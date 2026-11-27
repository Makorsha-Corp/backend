"""Workspace DAO"""

from sqlalchemy.orm import Session

from app.dao.base import BaseDAO
from app.models.workspace import Workspace
from app.schemas.workspace import WorkspaceCreate, WorkspaceUpdate


class WorkspaceDAO(BaseDAO[Workspace, WorkspaceCreate, WorkspaceUpdate]):
    """DAO for workspace operations"""

    def get_by_slug(self, db: Session, *, slug: str) -> Workspace | None:
        """Get workspace by slug"""
        return db.query(Workspace).filter(Workspace.slug == slug).first()

workspace_dao = WorkspaceDAO(Workspace)
