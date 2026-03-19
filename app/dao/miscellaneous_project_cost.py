"""DAO operations for MiscellaneousProjectCost model

SECURITY NOTICE:
This DAO handles workspace-scoped data. All query methods MUST filter by workspace_id
to prevent unauthorized cross-workspace data access.
"""
from typing import List
from sqlalchemy.orm import Session
from app.dao.base import BaseDAO
from app.models.miscellaneous_project_cost import MiscellaneousProjectCost
from app.schemas.miscellaneous_project_cost import MiscellaneousProjectCostCreate, MiscellaneousProjectCostUpdate


class DAOMiscellaneousProjectCost(BaseDAO[MiscellaneousProjectCost, MiscellaneousProjectCostCreate, MiscellaneousProjectCostUpdate]):
    """DAO operations for MiscellaneousProjectCost model (workspace-scoped)"""

    def get_by_project(
        self, db: Session, *, project_id: int, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[MiscellaneousProjectCost]:
        """
        Get costs by project ID (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            project_id: Project ID to filter by
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of miscellaneous costs belonging to the workspace
        """
        return (
            db.query(MiscellaneousProjectCost)
            .filter(
                MiscellaneousProjectCost.workspace_id == workspace_id,  # SECURITY: workspace isolation
                MiscellaneousProjectCost.project_id == project_id
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_component(
        self, db: Session, *, project_component_id: int, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[MiscellaneousProjectCost]:
        """
        Get costs by project component ID (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            project_component_id: Project component ID to filter by
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of miscellaneous costs belonging to the workspace
        """
        return (
            db.query(MiscellaneousProjectCost)
            .filter(
                MiscellaneousProjectCost.workspace_id == workspace_id,  # SECURITY: workspace isolation
                MiscellaneousProjectCost.project_component_id == project_component_id
            )
            .offset(skip)
            .limit(limit)
            .all()
        )


miscellaneous_project_cost_dao = DAOMiscellaneousProjectCost(MiscellaneousProjectCost)
