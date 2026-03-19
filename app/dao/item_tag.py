"""Item tag DAO operations"""
from sqlalchemy.orm import Session
from typing import List, Optional
from app.dao.base import BaseDAO
from app.models.item_tag import ItemTag
from app.schemas.item_tag import ItemTagCreate, ItemTagUpdate


class ItemTagDAO(BaseDAO[ItemTag, ItemTagCreate, ItemTagUpdate]):
    """DAO operations for ItemTag model"""

    def get_by_code_in_workspace(
        self, db: Session, *, workspace_id: int, tag_code: str
    ) -> Optional[ItemTag]:
        """
        Get tag by code within workspace (SECURITY-CRITICAL)

        Args:
            db: Database session
            workspace_id: Workspace ID to filter by
            tag_code: Tag code to search for

        Returns:
            Tag with matching code or None
        """
        return (
            db.query(ItemTag)
            .filter(
                ItemTag.workspace_id == workspace_id,
                ItemTag.tag_code == tag_code
            )
            .first()
        )

    def get_system_tags_in_workspace(
        self, db: Session, *, workspace_id: int
    ) -> List[ItemTag]:
        """
        Get all system tags within workspace

        Args:
            db: Database session
            workspace_id: Workspace ID to filter by

        Returns:
            List of system tags in workspace
        """
        return (
            db.query(ItemTag)
            .filter(
                ItemTag.workspace_id == workspace_id,
                ItemTag.is_system_tag == True,
                ItemTag.is_active == True
            )
            .all()
        )

    def get_user_tags_in_workspace(
        self, db: Session, *, workspace_id: int
    ) -> List[ItemTag]:
        """
        Get all user-created tags within workspace

        Args:
            db: Database session
            workspace_id: Workspace ID to filter by

        Returns:
            List of user-created tags in workspace
        """
        return (
            db.query(ItemTag)
            .filter(
                ItemTag.workspace_id == workspace_id,
                ItemTag.is_system_tag == False,
                ItemTag.is_active == True
            )
            .all()
        )

    def get_active_tags_in_workspace(
        self, db: Session, *, workspace_id: int
    ) -> List[ItemTag]:
        """
        Get all active tags within workspace

        Args:
            db: Database session
            workspace_id: Workspace ID to filter by

        Returns:
            List of active tags in workspace
        """
        return (
            db.query(ItemTag)
            .filter(
                ItemTag.workspace_id == workspace_id,
                ItemTag.is_active == True
            )
            .order_by(ItemTag.is_system_tag.desc(), ItemTag.name)
            .all()
        )

    def increment_usage_count(
        self, db: Session, *, tag_id: int, workspace_id: int
    ) -> ItemTag:
        """
        Increment usage count for a tag (SECURITY-CRITICAL)

        Args:
            db: Database session
            tag_id: Tag ID
            workspace_id: Workspace ID to filter by

        Returns:
            Updated tag
        """
        tag = self.get_by_id_and_workspace(db, id=tag_id, workspace_id=workspace_id)
        if tag:
            tag.usage_count += 1
            db.flush()
        return tag

    def decrement_usage_count(
        self, db: Session, *, tag_id: int, workspace_id: int
    ) -> ItemTag:
        """
        Decrement usage count for a tag (SECURITY-CRITICAL)

        Args:
            db: Database session
            tag_id: Tag ID
            workspace_id: Workspace ID to filter by

        Returns:
            Updated tag
        """
        tag = self.get_by_id_and_workspace(db, id=tag_id, workspace_id=workspace_id)
        if tag and tag.usage_count > 0:
            tag.usage_count -= 1
            db.flush()
        return tag


item_tag_dao = ItemTagDAO(ItemTag)
