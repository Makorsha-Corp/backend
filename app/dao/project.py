"""DAO operations for Project model (workspace-scoped)"""
from typing import List
from sqlalchemy.orm import Session
from app.dao.base import BaseDAO
from app.models.project import Project
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.models.enums import ProjectStatusEnum


class DAOProject(BaseDAO[Project, ProjectCreate, ProjectUpdate]):
    """
    DAO operations for Project model.

    SECURITY: All methods MUST filter by workspace_id to prevent cross-workspace data access.
    """

    def get_by_factory(
        self, db: Session, *, factory_id: int, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[Project]:
        """
        Get projects by factory ID (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            factory_id: Factory ID
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of projects for the factory in the workspace
        """
        return (
            db.query(Project)
            .filter(
                Project.workspace_id == workspace_id,  # SECURITY: workspace isolation
                Project.factory_id == factory_id
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_status(
        self, db: Session, *, status: ProjectStatusEnum, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[Project]:
        """
        Get projects by status (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            status: Project status
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of projects with the status in the workspace

        Security Note:
            WITHOUT workspace filter, this would return ALL projects with this status from ALL workspaces!
            This is a SEVERE data leak that exposes sensitive project information.
        """
        return (
            db.query(Project)
            .filter(
                Project.workspace_id == workspace_id,  # SECURITY: CRITICAL filter
                Project.status == status
            )
            .offset(skip)
            .limit(limit)
            .all()
        )


project_dao = DAOProject(Project)
