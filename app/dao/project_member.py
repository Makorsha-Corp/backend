"""Project member DAO. SECURITY: All queries MUST filter by workspace_id."""
from typing import List, Optional
from sqlalchemy.orm import Session
from app.dao.base import BaseDAO
from app.models.project_member import ProjectMember
from app.schemas.project import ProjectMemberCreate


class ProjectMemberDAO(BaseDAO[ProjectMember, ProjectMemberCreate, ProjectMemberCreate]):
    def get_by_project(
        self, db: Session, *, project_id: int, workspace_id: int
    ) -> List[ProjectMember]:
        return (
            db.query(ProjectMember)
            .filter(
                ProjectMember.project_id == project_id,
                ProjectMember.workspace_id == workspace_id,
            )
            .order_by(ProjectMember.assigned_at)
            .all()
        )

    def get_by_project_and_user(
        self, db: Session, *, project_id: int, user_id: int, workspace_id: int
    ) -> Optional[ProjectMember]:
        return (
            db.query(ProjectMember)
            .filter(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == user_id,
                ProjectMember.workspace_id == workspace_id,
            )
            .first()
        )

project_member_dao = ProjectMemberDAO(ProjectMember)
