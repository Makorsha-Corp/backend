"""DAO operations"""
from typing import List
from sqlalchemy.orm import Session
from app.dao.base import BaseDAO
from app.models.project_component_item import ProjectComponentItem
from app.schemas.project_component_item import ProjectComponentItemCreate, ProjectComponentItemUpdate


class DAOProjectComponentItem(BaseDAO[ProjectComponentItem, ProjectComponentItemCreate, ProjectComponentItemUpdate]):
    """DAO operations for ProjectComponentItem model"""

    def get_by_component(
        self, db: Session, *, project_component_id: int, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[ProjectComponentItem]:
        """
        Get component items by project component ID (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            project_component_id: Project component ID
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of project component items belonging to the workspace
        """
        return (
            db.query(ProjectComponentItem)
            .filter(
                ProjectComponentItem.workspace_id == workspace_id,  # SECURITY: workspace isolation
                ProjectComponentItem.project_component_id == project_component_id
            )
            .offset(skip)
            .limit(limit)
            .all()
        )


project_component_item_dao = DAOProjectComponentItem(ProjectComponentItem)
