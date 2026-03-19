"""Item DAO operations (renamed from Part)"""
from sqlalchemy.orm import Session
from typing import List, Optional
from app.dao.base import BaseDAO
from app.models.item import Item
from app.schemas.item import ItemCreate, ItemUpdate


class ItemDAO(BaseDAO[Item, ItemCreate, ItemUpdate]):
    """DAO operations for Item model"""

    def search_by_name_in_workspace(
        self, db: Session, *, workspace_id: int, name: str, skip: int = 0, limit: int = 100
    ) -> List[Item]:
        """
        Search items by name within a workspace (SECURITY-CRITICAL)

        Args:
            db: Database session
            workspace_id: Workspace ID to filter by
            name: Item name search query
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of items matching the search within workspace
        """
        return (
            db.query(Item)
            .filter(
                Item.workspace_id == workspace_id,
                Item.name.ilike(f"%{name}%"),
                Item.is_active == True
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_sku_in_workspace(
        self, db: Session, *, workspace_id: int, sku: str
    ) -> Optional[Item]:
        """
        Get item by SKU within workspace (SECURITY-CRITICAL)

        Args:
            db: Database session
            workspace_id: Workspace ID to filter by
            sku: SKU to search for

        Returns:
            Item with matching SKU or None
        """
        return (
            db.query(Item)
            .filter(
                Item.workspace_id == workspace_id,
                Item.sku == sku
            )
            .first()
        )

    def get_active_items_in_workspace(
        self, db: Session, *, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[Item]:
        """
        Get only active items within workspace

        Args:
            db: Database session
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of active items in workspace
        """
        return (
            db.query(Item)
            .filter(
                Item.workspace_id == workspace_id,
                Item.is_active == True
            )
            .offset(skip)
            .limit(limit)
            .all()
        )


item_dao = ItemDAO(Item)
