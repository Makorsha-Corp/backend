"""
Project Service

Orchestrates project operations with transaction management.
"""
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session

from app.services.base_service import BaseService
from app.managers.project_manager import project_manager
from app.models.project import Project
from app.models.project_event import ProjectEvent
from app.models.project_member import ProjectMember
from app.models.enums import ProjectVisibilityEnum
from app.models.profile import Profile
from app.schemas.project import ProjectCreate, ProjectUpdate


class ProjectService(BaseService):
    """Service for project workflows."""

    def __init__(self):
        super().__init__()
        self.project_manager = project_manager

    def create_project(
        self,
        db: Session,
        project_in: ProjectCreate,
        workspace_id: int,
        user_id: int,
    ) -> Project:
        try:
            project = self.project_manager.create_project(
                session=db,
                project_data=project_in,
                workspace_id=workspace_id,
                user_id=user_id,
            )
            self._commit_transaction(db)
            db.refresh(project)
            return project
        except Exception:
            self._rollback_transaction(db)
            raise

    def get_project(
        self,
        db: Session,
        project_id: int,
        workspace_id: int,
        user_id: int,
    ) -> Project:
        return self.project_manager.get_project(
            session=db,
            project_id=project_id,
            workspace_id=workspace_id,
            user_id=user_id,
        )

    def list_projects(
        self,
        db: Session,
        workspace_id: int,
        user_id: int,
        factory_id: Optional[int] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Project]:
        return self.project_manager.list_projects(
            session=db,
            workspace_id=workspace_id,
            user_id=user_id,
            factory_id=factory_id,
            status=status,
            skip=skip,
            limit=limit,
        )

    def update_project(
        self,
        db: Session,
        project_id: int,
        project_in: ProjectUpdate,
        workspace_id: int,
        user_id: int,
    ) -> Project:
        try:
            project = self.project_manager.update_project(
                session=db,
                project_id=project_id,
                project_data=project_in,
                workspace_id=workspace_id,
                user_id=user_id,
            )
            self._commit_transaction(db)
            db.refresh(project)
            return project
        except Exception:
            self._rollback_transaction(db)
            raise

    def delete_project(
        self,
        db: Session,
        project_id: int,
        workspace_id: int,
        user_id: int,
    ) -> Project:
        try:
            project = self.project_manager.delete_project(
                session=db,
                project_id=project_id,
                workspace_id=workspace_id,
                user_id=user_id,
            )
            self._commit_transaction(db)
            db.refresh(project)
            return project
        except Exception:
            self._rollback_transaction(db)
            raise

    def list_events(
        self,
        db: Session,
        project_id: int,
        workspace_id: int,
        user_id: int,
    ) -> List[Tuple[ProjectEvent, Optional[Profile]]]:
        return self.project_manager.list_events(
            session=db,
            project_id=project_id,
            workspace_id=workspace_id,
            user_id=user_id,
        )

    def list_members(
        self,
        db: Session,
        project_id: int,
        workspace_id: int,
        user_id: int,
    ) -> List[ProjectMember]:
        return self.project_manager.list_members(
            session=db,
            project_id=project_id,
            workspace_id=workspace_id,
            user_id=user_id,
        )

    def add_member(
        self,
        db: Session,
        project_id: int,
        member_user_id: int,
        workspace_id: int,
        assigned_by: int,
    ) -> ProjectMember:
        try:
            member = self.project_manager.add_member(
                session=db,
                project_id=project_id,
                member_user_id=member_user_id,
                workspace_id=workspace_id,
                assigned_by=assigned_by,
            )
            self._commit_transaction(db)
            db.refresh(member)
            return member
        except Exception:
            self._rollback_transaction(db)
            raise

    def remove_member(
        self,
        db: Session,
        project_id: int,
        member_user_id: int,
        workspace_id: int,
        performed_by: int,
    ) -> None:
        try:
            self.project_manager.remove_member(
                session=db,
                project_id=project_id,
                member_user_id=member_user_id,
                workspace_id=workspace_id,
                performed_by=performed_by,
            )
            self._commit_transaction(db)
        except Exception:
            self._rollback_transaction(db)
            raise

    def set_visibility(
        self,
        db: Session,
        project_id: int,
        visibility: ProjectVisibilityEnum,
        workspace_id: int,
        user_id: int,
    ) -> Project:
        try:
            project = self.project_manager.set_visibility(
                session=db,
                project_id=project_id,
                visibility=visibility,
                workspace_id=workspace_id,
                user_id=user_id,
            )
            self._commit_transaction(db)
            db.refresh(project)
            return project
        except Exception:
            self._rollback_transaction(db)
            raise


project_service = ProjectService()
