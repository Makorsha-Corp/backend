"""DAO operations for ProjectComponentTask model

SECURITY NOTICE:
This DAO handles workspace-scoped data. All query methods MUST filter by workspace_id
to prevent unauthorized cross-workspace data access.
"""
from typing import List
from sqlalchemy.orm import Session
from app.dao.base import BaseDAO
from app.models.project_component_task import ProjectComponentTask
from app.schemas.project_component_task import ProjectComponentTaskCreate, ProjectComponentTaskUpdate


class DAOProjectComponentTask(BaseDAO[ProjectComponentTask, ProjectComponentTaskCreate, ProjectComponentTaskUpdate]):
    """DAO operations for ProjectComponentTask model (workspace-scoped)"""

    def get_by_component(
        self, db: Session, *, project_component_id: int, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[ProjectComponentTask]:
        """
        Get tasks by project component ID (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            project_component_id: Project component ID to filter by
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of tasks belonging to the workspace
        """
        return (
            db.query(ProjectComponentTask)
            .filter(
                ProjectComponentTask.workspace_id == workspace_id,  # SECURITY: workspace isolation
                ProjectComponentTask.project_component_id == project_component_id
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_incomplete_tasks(
        self, db: Session, *, project_component_id: int, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[ProjectComponentTask]:
        """
        Get incomplete tasks by project component ID (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            project_component_id: Project component ID to filter by
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of incomplete tasks belonging to the workspace
        """
        return (
            db.query(ProjectComponentTask)
            .filter(
                ProjectComponentTask.workspace_id == workspace_id,  # SECURITY: workspace isolation
                ProjectComponentTask.project_component_id == project_component_id,
                ProjectComponentTask.is_completed == False
            )
            .offset(skip)
            .limit(limit)
            .all()
        )


project_component_task_dao = DAOProjectComponentTask(ProjectComponentTask)
