"""Item DAO operations (renamed from Part)"""
from sqlalchemy.orm import Session, Query
from sqlalchemy import func, or_, desc
from typing import List, Optional, Tuple
from app.dao.base import BaseDAO
from app.models.item import Item
from app.models.item_tag import ItemTag
from app.models.item_tag_assignment import ItemTagAssignment
from app.schemas.item import ItemCreate, ItemUpdate
from app.utils.item_name_normalize import (
    normalize_item_name,
    MIN_SIMILAR_NAME_LENGTH,
    SIMILARITY_THRESHOLD,
)


def _apply_item_catalog_filters(
    query: Query,
    *,
    workspace_id: int,
    search: Optional[str] = None,
    unit: Optional[str] = None,
    tag_ids: Optional[List[int]] = None,
) -> Query:
    """Shared filters for paginated item catalog list/count."""
    query = query.filter(
        Item.workspace_id == workspace_id,
        Item.is_active == True,
    )

    if unit:
        query = query.filter(Item.unit == unit)

    if tag_ids:
        query = query.join(
            ItemTagAssignment,
            ItemTagAssignment.item_id == Item.id,
        ).filter(
            ItemTagAssignment.workspace_id == workspace_id,
            ItemTagAssignment.tag_id.in_(tag_ids),
        )

    if search and search.strip():
        term = search.strip()
        clauses = [
            Item.name.ilike(f"%{term}%"),
            Item.description.ilike(f"%{term}%"),
            Item.sku.ilike(f"%{term}%"),
            Item.unit.ilike(f"%{term}%"),
        ]
        if term.isdigit():
            clauses.append(Item.id == int(term))

        session = query.session
        tag_name_match = (
            session.query(ItemTagAssignment.item_id)
            .join(ItemTag, ItemTag.id == ItemTagAssignment.tag_id)
            .filter(
                ItemTagAssignment.workspace_id == workspace_id,
                ItemTag.name.ilike(f"%{term}%"),
            )
        )
        clauses.append(Item.id.in_(tag_name_match))
        query = query.filter(or_(*clauses))

    return query


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

    def list_active_items_filtered(
        self,
        db: Session,
        *,
        workspace_id: int,
        skip: int = 0,
        limit: int = 100,
        search: Optional[str] = None,
        unit: Optional[str] = None,
        tag_ids: Optional[List[int]] = None,
    ) -> List[Item]:
        query = db.query(Item)
        query = _apply_item_catalog_filters(
            query,
            workspace_id=workspace_id,
            search=search,
            unit=unit,
            tag_ids=tag_ids,
        )
        return query.distinct(Item.id).order_by(Item.id).offset(skip).limit(limit).all()

    def count_active_items_filtered(
        self,
        db: Session,
        *,
        workspace_id: int,
        search: Optional[str] = None,
        unit: Optional[str] = None,
        tag_ids: Optional[List[int]] = None,
    ) -> int:
        filtered_ids = (
            _apply_item_catalog_filters(
                db.query(Item.id),
                workspace_id=workspace_id,
                search=search,
                unit=unit,
                tag_ids=tag_ids,
            )
            .distinct()
            .subquery()
        )
        return int(db.query(func.count()).select_from(filtered_ids).scalar() or 0)

    def distinct_units_in_workspace(self, db: Session, *, workspace_id: int) -> List[str]:
        rows = (
            db.query(Item.unit)
            .filter(
                Item.workspace_id == workspace_id,
                Item.is_active == True,
            )
            .distinct()
            .order_by(Item.unit)
            .all()
        )
        return [row[0] for row in rows if row[0]]

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
