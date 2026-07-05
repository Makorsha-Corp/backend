"""Item DAO operations (renamed from Part)"""
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, desc
from typing import List, Optional, Tuple
from app.dao.base import BaseDAO
from app.models.item import Item
from app.schemas.item import ItemCreate, ItemUpdate
from app.utils.item_name_normalize import (
    normalize_item_name,
    MIN_SIMILAR_NAME_LENGTH,
    SIMILARITY_THRESHOLD,
)


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

    def find_similar_by_name_in_workspace(
        self,
        db: Session,
        *,
        workspace_id: int,
        name: str,
        limit: int = 5,
        exclude_item_id: Optional[int] = None,
    ) -> List[Tuple[Item, float]]:
        """
        Find active items with similar normalized names (SECURITY-CRITICAL).

        Uses pg_trgm similarity on name_normalized plus exact normalized matches.
        """
        normalized = normalize_item_name(name)
        if len(normalized) < MIN_SIMILAR_NAME_LENGTH:
            return []

        score_expr = func.similarity(Item.name_normalized, normalized)

        query = (
            db.query(Item, score_expr.label("score"))
            .filter(
                Item.workspace_id == workspace_id,
                Item.is_active == True,
                or_(
                    Item.name_normalized == normalized,
                    score_expr >= SIMILARITY_THRESHOLD,
                ),
            )
        )

        if exclude_item_id is not None:
            query = query.filter(Item.id != exclude_item_id)

        return (
            query.order_by(desc("score"))
            .limit(limit)
            .all()
        )


item_dao = ItemDAO(Item)
