"""Item tag DAO operations"""

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import set_committed_value

from app.dao.base import BaseDAO
from app.models.item_tag import ItemTag
from app.schemas.item_tag import ItemTagCreate, ItemTagUpdate


class ItemTagDAO(BaseDAO[ItemTag, ItemTagCreate, ItemTagUpdate]):
    """DAO operations for ItemTag model"""

    def get_by_code_in_workspace(
        self, db: Session, *, workspace_id: int, tag_code: str
    ) -> ItemTag | None:
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
    ) -> list[ItemTag]:
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
            .order_by(func.lower(ItemTag.name).asc(), ItemTag.id.asc())
            .all()
        )

    def get_active_tags_in_workspace(
        self, db: Session, *, workspace_id: int
    ) -> list[ItemTag]:
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
            .order_by(
                ItemTag.is_system_tag.desc(),
                func.lower(ItemTag.name).asc(),
                ItemTag.id.asc(),
            )
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
            # Relative update in the database (BUG-931): the flush sends
            # SET usage_count = usage_count + 1 and the attribute is reloaded
            # from the stored result, never computed from the loaded object.
            tag.usage_count = ItemTag.usage_count + 1
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
        if tag:
            # Relative update in the database (BUG-931): the decrease and the
            # "not below 0" check both use the stored value.
            stored = db.execute(
                update(ItemTag)
                .where(
                    ItemTag.id == tag.id,
                    ItemTag.workspace_id == workspace_id,
                    ItemTag.usage_count > 0,
                )
                .values(usage_count=ItemTag.usage_count - 1)
                .returning(ItemTag.usage_count)
                .execution_options(synchronize_session=False, autoflush=False)
            ).scalar_one_or_none()
            if stored is not None:
                # Written: reload from the database on next access
                # (savepoint-safe) and flush like before.
                db.expire(tag, ["usage_count"])
                db.flush()
            else:
                # Stored value is 0 or below: nothing written, nothing
                # flushed; the returned tag shows the stored value.
                stored = db.execute(
                    select(ItemTag.usage_count)
                    .where(ItemTag.id == tag.id)
                    .execution_options(autoflush=False)
                ).scalar_one()
                set_committed_value(tag, "usage_count", stored)
        return tag


item_tag_dao = ItemTagDAO(ItemTag)
