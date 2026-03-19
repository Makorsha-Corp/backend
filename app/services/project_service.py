"""
Project Service

Orchestrates project operations with transaction management.
"""
from typing import List, Optional
from sqlalchemy.orm import Session

from app.services.base_service import BaseService
from app.managers.project_manager import project_manager
from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectUpdate


class ProjectService(BaseService):
    """
    Service for project workflows.

    Handles transaction management for project operations.
    """

    def __init__(self):
        super().__init__()
        self.project_manager = project_manager

    def create_project(
        self,
        db: Session,
        project_in: ProjectCreate,
        workspace_id: int,
        user_id: int
    ) -> Project:
        """
        Create new project with transaction management.

        Args:
            db: Database session
            project_in: Project creation data
            workspace_id: Workspace ID
            user_id: User creating the project

        Returns:
            Created project

        Raises:
            HTTPException: If validation fails
        """
        try:
            project = self.project_manager.create_project(
                session=db,
                project_data=project_in,
                workspace_id=workspace_id,
                user_id=user_id
            )
            self._commit_transaction(db)
            db.refresh(project)
            return project
        except Exception as e:
            self._rollback_transaction(db)
            raise

    def get_project(
        self,
        db: Session,
        project_id: int,
        workspace_id: int
    ) -> Project:
        """
        Get project by ID.

        Args:
            db: Database session
            project_id: Project ID
            workspace_id: Workspace ID

        Returns:
            Project
        """
        return self.project_manager.get_project(
            session=db,
            project_id=project_id,
            workspace_id=workspace_id
        )

    def list_projects(
        self,
        db: Session,
        workspace_id: int,
        factory_id: Optional[int] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Project]:
        """
        List projects with optional filters.

        Args:
            db: Database session
            workspace_id: Workspace ID
            factory_id: Optional factory filter
            status: Optional status filter
            skip: Number of records to skip
            limit: Maximum number of records

        Returns:
            List of projects
        """
        return self.project_manager.list_projects(
            session=db,
            workspace_id=workspace_id,
            factory_id=factory_id,
            status=status,
            skip=skip,
            limit=limit
        )

    def update_project(
        self,
        db: Session,
        project_id: int,
        project_in: ProjectUpdate,
        workspace_id: int,
        user_id: int
    ) -> Project:
        """
        Update project with transaction management.

        Args:
            db: Database session
            project_id: Project ID
            project_in: Update data
            workspace_id: Workspace ID
            user_id: User updating the project

        Returns:
            Updated project
        """
        try:
            project = self.project_manager.update_project(
                session=db,
                project_id=project_id,
                project_data=project_in,
                workspace_id=workspace_id,
                user_id=user_id
            )
            self._commit_transaction(db)
            db.refresh(project)
            return project
        except Exception as e:
            self._rollback_transaction(db)
            raise

    def delete_project(
        self,
        db: Session,
        project_id: int,
        workspace_id: int,
        user_id: int
    ) -> Project:
        """
        Soft delete project with transaction management.

        Args:
            db: Database session
            project_id: Project ID
            workspace_id: Workspace ID
            user_id: User deleting the project

        Returns:
            Deleted project
        """
        try:
            project = self.project_manager.delete_project(
                session=db,
                project_id=project_id,
                workspace_id=workspace_id,
                user_id=user_id
            )
            self._commit_transaction(db)
            db.refresh(project)
            return project
        except Exception as e:
            self._rollback_transaction(db)
            raise


project_service = ProjectService()
