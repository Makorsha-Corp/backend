"""DAO operations"""
from typing import List
from sqlalchemy.orm import Session
from app.dao.base import BaseDAO
from app.models.project_component import ProjectComponent
from app.schemas.project_component import ProjectComponentCreate, ProjectComponentUpdate


class DAOProjectComponent(BaseDAO[ProjectComponent, ProjectComponentCreate, ProjectComponentUpdate]):
    """DAO operations for ProjectComponent model"""

    def get_by_project(
        self, db: Session, *, project_id: int, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[ProjectComponent]:
        """
        Get components by project ID (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            project_id: Project ID
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of project components belonging to the workspace
        """
        return (
            db.query(ProjectComponent)
            .filter(
                ProjectComponent.workspace_id == workspace_id,  # SECURITY: workspace isolation
                ProjectComponent.project_id == project_id
            )
            .offset(skip)
            .limit(limit)
            .all()
        )


project_component_dao = DAOProjectComponent(ProjectComponent)
