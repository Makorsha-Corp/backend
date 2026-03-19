"""
Project Manager

Business logic for project operations.
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from datetime import datetime

from app.managers.base_manager import BaseManager
from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.dao.project import project_dao
from app.dao.factory import factory_dao


class ProjectManager(BaseManager[Project]):
    """
    Manager for project business logic.

    Handles CRUD operations for projects with workspace isolation and validation.
    """

    def __init__(self):
        super().__init__(Project)
        self.project_dao = project_dao
        self.factory_dao = factory_dao

    def create_project(
        self,
        session: Session,
        project_data: ProjectCreate,
        workspace_id: int,
        user_id: int
    ) -> Project:
        """
        Create new project.

        Args:
            session: Database session
            project_data: Project creation data
            workspace_id: Workspace ID
            user_id: User creating the project

        Returns:
            Created project

        Raises:
            HTTPException: If factory not found or validation fails
        """
        # Validate factory exists in workspace
        factory = self.factory_dao.get_by_id_and_workspace(
            session, id=project_data.factory_id, workspace_id=workspace_id
        )
        if not factory:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Factory with ID {project_data.factory_id} not found"
            )

        # Check if factory is deleted
        if factory.is_deleted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot create project for deleted factory"
            )

        # Create project with audit fields
        project_dict = project_data.model_dump()
        project_dict['workspace_id'] = workspace_id
        project_dict['created_by'] = user_id
        project_dict['is_active'] = True
        project_dict['is_deleted'] = False

        project = self.project_dao.create(session, obj_in=project_dict)
        return project

    def get_project(
        self,
        session: Session,
        project_id: int,
        workspace_id: int
    ) -> Project:
        """
        Get project by ID.

        Args:
            session: Database session
            project_id: Project ID
            workspace_id: Workspace ID

        Returns:
            Project

        Raises:
            HTTPException: If project not found
        """
        project = self.project_dao.get_by_id_and_workspace(
            session, id=project_id, workspace_id=workspace_id
        )
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project with ID {project_id} not found"
            )
        return project

    def list_projects(
        self,
        session: Session,
        workspace_id: int,
        factory_id: Optional[int] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Project]:
        """
        List projects with optional filters.

        Args:
            session: Database session
            workspace_id: Workspace ID
            factory_id: Optional factory filter
            status: Optional status filter
            skip: Number of records to skip
            limit: Maximum number of records

        Returns:
            List of projects
        """
        if factory_id:
            return self.project_dao.get_by_factory(
                session, factory_id=factory_id, workspace_id=workspace_id,
                skip=skip, limit=limit
            )
        elif status:
            from app.models.enums import ProjectStatusEnum
            return self.project_dao.get_by_status(
                session, status=ProjectStatusEnum(status), workspace_id=workspace_id,
                skip=skip, limit=limit
            )
        else:
            return self.project_dao.get_by_workspace(
                session, workspace_id=workspace_id, skip=skip, limit=limit
            )

    def update_project(
        self,
        session: Session,
        project_id: int,
        project_data: ProjectUpdate,
        workspace_id: int,
        user_id: int
    ) -> Project:
        """
        Update project.

        Args:
            session: Database session
            project_id: Project ID
            project_data: Update data
            workspace_id: Workspace ID
            user_id: User updating the project

        Returns:
            Updated project

        Raises:
            HTTPException: If project not found
        """
        # Get existing project
        project = self.get_project(session, project_id, workspace_id)

        # Check if project is deleted
        if project.is_deleted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot update deleted project"
            )

        # Update project with audit fields
        update_dict = project_data.model_dump(exclude_unset=True)
        update_dict['updated_by'] = user_id
        update_dict['updated_at'] = datetime.utcnow()

        updated_project = self.project_dao.update(
            session, db_obj=project, obj_in=update_dict
        )
        return updated_project

    def delete_project(
        self,
        session: Session,
        project_id: int,
        workspace_id: int,
        user_id: int
    ) -> Project:
        """
        Soft delete project.

        Args:
            session: Database session
            project_id: Project ID
            workspace_id: Workspace ID
            user_id: User deleting the project

        Returns:
            Deleted project

        Raises:
            HTTPException: If project not found
        """
        # Get existing project
        project = self.get_project(session, project_id, workspace_id)

        # Check if already deleted
        if project.is_deleted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Project is already deleted"
            )

        # Soft delete
        project.is_deleted = True
        project.deleted_at = datetime.utcnow()
        project.deleted_by = user_id
        session.add(project)
        session.flush()

        return project


project_manager = ProjectManager()
