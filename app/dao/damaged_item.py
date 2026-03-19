"""DAO operations"""
from typing import List
from sqlalchemy.orm import Session
from app.dao.base import BaseDAO
from app.models.damaged_item import DamagedItem
from app.schemas.damaged_item import DamagedItemCreate, DamagedItemUpdate


class DAODamagedItem(BaseDAO[DamagedItem, DamagedItemCreate, DamagedItemUpdate]):
    """DAO operations for DamagedItem model"""

    def get_by_factory(
        self, db: Session, *, factory_id: int, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[DamagedItem]:
        """
        Get damaged items by factory ID (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            factory_id: Factory ID
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of damaged items belonging to the workspace
        """
        return (
            db.query(DamagedItem)
            .filter(
                DamagedItem.workspace_id == workspace_id,  # SECURITY: workspace isolation
                DamagedItem.factory_id == factory_id
            )
            .offset(skip)
            .limit(limit)
            .all()
        )


damaged_item_dao = DAODamagedItem(DamagedItem)
