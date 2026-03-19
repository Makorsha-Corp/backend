"""Item tag assignment DAO operations"""
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List, Optional
from app.dao.base import BaseDAO
from app.models.item_tag_assignment import ItemTagAssignment
from app.models.item_tag import ItemTag
from app.schemas.item_tag_assignment import ItemTagAssignmentCreate, ItemTagAssignmentResponse


class ItemTagAssignmentDAO(BaseDAO[ItemTagAssignment, ItemTagAssignmentCreate, ItemTagAssignmentResponse]):
    """DAO operations for ItemTagAssignment model"""

    def get_tags_for_item(
        self, db: Session, *, item_id: int, workspace_id: int
    ) -> List[ItemTag]:
        """
        Get all tags assigned to an item (SECURITY-CRITICAL)

        Args:
            db: Database session
            item_id: Item ID
            workspace_id: Workspace ID to filter by

        Returns:
            List of tags assigned to the item
        """
        return (
            db.query(ItemTag)
            .join(ItemTagAssignment, ItemTag.id == ItemTagAssignment.tag_id)
            .filter(
                ItemTagAssignment.item_id == item_id,
                ItemTagAssignment.workspace_id == workspace_id,
                ItemTag.is_active == True
            )
            .all()
        )

    def get_items_with_tag(
        self, db: Session, *, tag_id: int, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[int]:
        """
        Get all item IDs that have a specific tag (SECURITY-CRITICAL)

        Args:
            db: Database session
            tag_id: Tag ID
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of item IDs with the tag
        """
        results = (
            db.query(ItemTagAssignment.item_id)
            .filter(
                ItemTagAssignment.tag_id == tag_id,
                ItemTagAssignment.workspace_id == workspace_id
            )
            .offset(skip)
            .limit(limit)
            .all()
        )
        return [r[0] for r in results]

    def get_items_with_tags(
        self, db: Session, *, tag_codes: List[str], workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[int]:
        """
        Get item IDs that have ALL specified tags (SECURITY-CRITICAL)

        Args:
            db: Database session
            tag_codes: List of tag codes
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of item IDs with all specified tags
        """
        # Build query with multiple tag filters
        query = db.query(ItemTagAssignment.item_id)

        for tag_code in tag_codes:
            subquery = (
                db.query(ItemTagAssignment.item_id)
                .join(ItemTag, ItemTag.id == ItemTagAssignment.tag_id)
                .filter(
                    ItemTag.tag_code == tag_code,
                    ItemTag.workspace_id == workspace_id,
                    ItemTagAssignment.workspace_id == workspace_id
                )
            )
            query = query.filter(ItemTagAssignment.item_id.in_(subquery))

        results = query.offset(skip).limit(limit).all()
        return [r[0] for r in results]

    def assignment_exists(
        self, db: Session, *, item_id: int, tag_id: int, workspace_id: int
    ) -> bool:
        """
        Check if tag is already assigned to item (SECURITY-CRITICAL)

        Args:
            db: Database session
            item_id: Item ID
            tag_id: Tag ID
            workspace_id: Workspace ID to filter by

        Returns:
            True if assignment exists, False otherwise
        """
        return (
            db.query(ItemTagAssignment)
            .filter(
                ItemTagAssignment.item_id == item_id,
                ItemTagAssignment.tag_id == tag_id,
                ItemTagAssignment.workspace_id == workspace_id
            )
            .first()
        ) is not None

    def remove_assignment(
        self, db: Session, *, item_id: int, tag_id: int, workspace_id: int
    ) -> Optional[ItemTagAssignment]:
        """
        Remove tag assignment from item (SECURITY-CRITICAL)

        Args:
            db: Database session
            item_id: Item ID
            tag_id: Tag ID
            workspace_id: Workspace ID to filter by

        Returns:
            Removed assignment or None
        """
        assignment = (
            db.query(ItemTagAssignment)
            .filter(
                ItemTagAssignment.item_id == item_id,
                ItemTagAssignment.tag_id == tag_id,
                ItemTagAssignment.workspace_id == workspace_id
            )
            .first()
        )

        if assignment:
            db.delete(assignment)
            db.flush()

        return assignment

    def remove_all_tags_from_item(
        self, db: Session, *, item_id: int, workspace_id: int
    ) -> int:
        """
        Remove all tag assignments from an item (SECURITY-CRITICAL)

        Args:
            db: Database session
            item_id: Item ID
            workspace_id: Workspace ID to filter by

        Returns:
            Number of assignments removed
        """
        count = (
            db.query(ItemTagAssignment)
            .filter(
                ItemTagAssignment.item_id == item_id,
                ItemTagAssignment.workspace_id == workspace_id
            )
            .delete()
        )
        db.flush()
        return count


item_tag_assignment_dao = ItemTagAssignmentDAO(ItemTagAssignment)
