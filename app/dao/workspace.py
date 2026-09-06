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

workspace_dao = WorkspaceDAO(Workspace)
