"""DAO operations"""
from typing import List, Optional
from sqlalchemy.orm import Session
from app.dao.base import BaseDAO
from app.models.storage_item import StorageItem
from app.schemas.storage_item import StorageItemCreate, StorageItemUpdate


class DAOStorageItem(BaseDAO[StorageItem, StorageItemCreate, StorageItemUpdate]):
    """DAO operations for StorageItem model"""

    def get_by_factory(
        self, db: Session, *, factory_id: int, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[StorageItem]:
        """
        Get storage items by factory ID (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            factory_id: Factory ID
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of storage items belonging to the workspace
        """
        return (
            db.query(StorageItem)
            .filter(
                StorageItem.workspace_id == workspace_id,  # SECURITY: workspace isolation
                StorageItem.factory_id == factory_id
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_factory_and_part(
        self, db: Session, *, factory_id: int, part_id: int, workspace_id: int
    ) -> Optional[StorageItem]:
        """
        Get storage item by factory and part ID (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            factory_id: Factory ID
            part_id: Part ID
            workspace_id: Workspace ID to filter by

        Returns:
            Storage item if found in workspace, None otherwise
        """
        return (
            db.query(StorageItem)
            .filter(
                StorageItem.workspace_id == workspace_id,  # SECURITY: workspace isolation
                StorageItem.factory_id == factory_id,
                StorageItem.part_id == part_id
            )
            .first()
        )


storage_item_dao = DAOStorageItem(StorageItem)
