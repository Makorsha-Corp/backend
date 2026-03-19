"""Item Service for orchestrating item workflows"""
from typing import List, Optional
from sqlalchemy.orm import Session
from app.services.base_service import BaseService
from app.managers.item_manager import item_manager
from app.models.item import Item
from app.models.profile import Profile
from app.schemas.item import ItemCreate, ItemUpdate, ItemWithTagsResponse
from app.core.exceptions import NotFoundError


class ItemService(BaseService):
    """
    Service for Item workflows.

    Handles:
    - Transaction boundaries (commit/rollback)
    - Item catalog operations
    - Error handling and exception translation
    """

    def __init__(self):
        super().__init__()
        self.item_manager = item_manager

    def create_item(
        self,
        db: Session,
        item_in: ItemCreate,
        workspace_id: int,
        user_id: int
    ) -> Item:
        """
        Create a new item.

        Args:
            db: Database session
            item_in: Item creation data
            workspace_id: Workspace ID
            user_id: User ID creating the item

        Returns:
            Created item

        Raises:
            ConflictError: If item with same name/SKU exists
        """
        try:
            # Create item using manager
            item = self.item_manager.create_item(
                session=db,
                item_data=item_in,
                workspace_id=workspace_id,
                user_id=user_id
            )

            # Commit transaction
            self._commit_transaction(db)
            db.refresh(item)

            return item

        except Exception as e:
            self._rollback_transaction(db)
            raise

    def get_item(
        self,
        db: Session,
        item_id: int,
        workspace_id: int
    ) -> Item:
        """
        Get item by ID.

        Args:
            db: Database session
            item_id: Item ID
            workspace_id: Workspace ID

        Returns:
            Item

        Raises:
            NotFoundError: If item not found
        """
        item = self.item_manager.get_item(db, item_id, workspace_id)
        if not item:
            raise NotFoundError(f"Item with ID {item_id} not found")
        return item

    def get_items(
        self,
        db: Session,
        workspace_id: int,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Item]:
        """
        Get all items with optional search and pagination.

        Args:
            db: Database session
            workspace_id: Workspace ID
            search: Optional search query for item name
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of items
        """
        return self.item_manager.search_items(
            session=db,
            workspace_id=workspace_id,
            name=search,
            skip=skip,
            limit=limit
        )

    def get_items_with_tags(
        self,
        db: Session,
        workspace_id: int,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[dict]:
        """
        Get all items with their tags included.

        Args:
            db: Database session
            workspace_id: Workspace ID
            search: Optional search query for item name
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of items with tags
        """
        items = self.item_manager.search_items(
            session=db,
            workspace_id=workspace_id,
            name=search,
            skip=skip,
            limit=limit
        )

        # Enrich items with tags
        items_with_tags = []
        for item in items:
            tags = self.item_manager.get_tags_for_item(
                session=db,
                item_id=item.id,
                workspace_id=workspace_id
            )

            item_dict = {
                "id": item.id,
                "workspace_id": item.workspace_id,
                "name": item.name,
                "description": item.description,
                "unit": item.unit,
                "sku": item.sku,
                "is_active": item.is_active,
                "created_at": item.created_at,
                "updated_at": item.updated_at,
                "created_by": item.created_by,
                "updated_by": item.updated_by,
                "tags": [
                    {
                        "id": tag.id,
                        "name": tag.name,
                        "tag_code": tag.tag_code,
                        "color": tag.color,
                        "icon": tag.icon,
                        "is_system_tag": tag.is_system_tag
                    }
                    for tag in tags
                ]
            }
            items_with_tags.append(item_dict)

        return items_with_tags

    def update_item(
        self,
        db: Session,
        item_id: int,
        item_in: ItemUpdate,
        workspace_id: int,
        user_id: int
    ) -> Item:
        """
        Update an existing item.

        Args:
            db: Database session
            item_id: Item ID
            item_in: Item update data
            workspace_id: Workspace ID
            user_id: User ID updating the item

        Returns:
            Updated item

        Raises:
            NotFoundError: If item not found
        """
        try:
            # Update item using manager
            item = self.item_manager.update_item(
                session=db,
                item_id=item_id,
                item_data=item_in,
                workspace_id=workspace_id,
                user_id=user_id
            )

            if not item:
                raise NotFoundError(f"Item with ID {item_id} not found")

            # Commit transaction
            self._commit_transaction(db)
            db.refresh(item)

            return item

        except NotFoundError:
            self._rollback_transaction(db)
            raise
        except Exception as e:
            self._rollback_transaction(db)
            raise

    def delete_item(
        self,
        db: Session,
        item_id: int,
        workspace_id: int,
        user_id: int
    ) -> None:
        """
        Delete an item (soft delete).

        Args:
            db: Database session
            item_id: Item ID
            workspace_id: Workspace ID
            user_id: User ID deleting the item

        Raises:
            NotFoundError: If item not found
        """
        try:
            # Check if item exists
            item = self.item_manager.get_item(db, item_id, workspace_id)
            if not item:
                raise NotFoundError(f"Item with ID {item_id} not found")

            # Delete item using manager
            self.item_manager.delete_item(
                session=db,
                item_id=item_id,
                workspace_id=workspace_id
            )

            # Commit transaction
            self._commit_transaction(db)

        except NotFoundError:
            self._rollback_transaction(db)
            raise
        except Exception as e:
            self._rollback_transaction(db)
            raise


# Singleton instance
item_service = ItemService()
