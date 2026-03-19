"""Item Manager for item business logic"""
from typing import List, Optional
from sqlalchemy.orm import Session
from app.managers.base_manager import BaseManager
from app.models.item import Item
from app.dao.item import item_dao
from app.dao.item_tag import item_tag_dao
from app.dao.item_tag_assignment import item_tag_assignment_dao
from app.schemas.item import ItemCreate, ItemUpdate


class ItemManager(BaseManager[Item]):
    """
    STANDALONE MANAGER: Simple item catalog operations.

    Manages: Item entity only (no children)

    Operations: CRUD, search

    Does NOT commit transactions - that's the service layer's responsibility.
    """

    def __init__(self):
        super().__init__(Item)
        self.item_dao = item_dao

    def create_item(
        self,
        session: Session,
        item_data: ItemCreate,
        workspace_id: int,
        user_id: int
    ) -> Item:
        """
        Create a new item with tag assignments.

        Args:
            session: Database session
            item_data: Item creation data (including tag_ids)
            workspace_id: Workspace ID (for multi-tenancy)
            user_id: User ID creating the item (for audit)

        Returns:
            Created item (not yet committed)

        Note:
            This method does NOT commit. The service layer must commit.
        """
        # Extract tag_ids before creating item
        tag_ids = item_data.tag_ids if hasattr(item_data, 'tag_ids') else []

        # Convert Pydantic model to dict and inject workspace/audit fields
        item_dict = item_data.model_dump(exclude={'tag_ids'})
        item_dict['workspace_id'] = workspace_id
        item_dict['created_by'] = user_id

        # Create the item
        item = self.item_dao.create(session, obj_in=item_dict)

        # Assign tags if provided
        if tag_ids:
            self._assign_tags_to_item(
                session=session,
                item_id=item.id,
                tag_ids=tag_ids,
                workspace_id=workspace_id,
                user_id=user_id
            )

        return item

    def update_item(
        self,
        session: Session,
        item_id: int,
        item_data: ItemUpdate,
        workspace_id: int,
        user_id: int
    ) -> Item:
        """
        Update an existing item with optional tag updates.

        Args:
            session: Database session
            item_id: Item ID
            item_data: Item update data (including optional tag_ids)
            workspace_id: Workspace ID (for multi-tenancy)
            user_id: User ID updating the item (for audit)

        Returns:
            Updated item (not yet committed)

        Raises:
            ValueError: If item not found or workspace mismatch

        Note:
            This method does NOT commit. The service layer must commit.
        """
        item = self.item_dao.get(session, id=item_id)
        if not item:
            raise ValueError(f"Item {item_id} not found")

        # Validate workspace ownership
        if item.workspace_id != workspace_id:
            raise ValueError(f"Item {item_id} does not belong to workspace {workspace_id}")

        # Extract tag_ids if provided
        tag_ids = None
        if hasattr(item_data, 'tag_ids') and item_data.tag_ids is not None:
            tag_ids = item_data.tag_ids

        # Inject updated_by for audit
        item_dict = item_data.model_dump(exclude_unset=True, exclude={'tag_ids'})
        item_dict['updated_by'] = user_id

        # Update the item
        updated_item = self.item_dao.update(session, db_obj=item, obj_in=item_dict)

        # Update tags if provided
        if tag_ids is not None:
            # Remove all existing tags
            item_tag_assignment_dao.remove_all_tags_from_item(
                session, item_id=item_id, workspace_id=workspace_id
            )
            # Assign new tags
            if tag_ids:
                self._assign_tags_to_item(
                    session=session,
                    item_id=item_id,
                    tag_ids=tag_ids,
                    workspace_id=workspace_id,
                    user_id=user_id
                )

        return updated_item

    def get_item(
        self,
        session: Session,
        item_id: int,
        workspace_id: int
    ) -> Optional[Item]:
        """
        Get item by ID within workspace.

        Args:
            session: Database session
            item_id: Item ID
            workspace_id: Workspace ID (for multi-tenancy)

        Returns:
            Item or None if not found or not in workspace

        Note:
            Returns None if item exists but doesn't belong to workspace (security)
        """
        item = self.item_dao.get(session, id=item_id)
        if item and item.workspace_id != workspace_id:
            # Item exists but not in this workspace - don't leak existence
            return None
        return item

    def search_items(
        self,
        session: Session,
        workspace_id: int,
        name: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Item]:
        """
        Search items by name or get all items within workspace.

        Args:
            session: Database session
            workspace_id: Workspace ID (for multi-tenancy)
            name: Optional search query for item name
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of items in workspace
        """
        if name:
            return self.item_dao.search_by_name_in_workspace(
                session,
                workspace_id=workspace_id,
                name=name,
                skip=skip,
                limit=limit
            )
        else:
            return self.item_dao.get_active_items_in_workspace(
                session,
                workspace_id=workspace_id,
                skip=skip,
                limit=limit
            )

    def delete_item(
        self,
        session: Session,
        item_id: int,
        workspace_id: int
    ) -> Item:
        """
        Delete a item (soft delete).

        Args:
            session: Database session
            item_id: Item ID
            workspace_id: Workspace ID (for multi-tenancy)

        Returns:
            Deleted item (not yet committed)

        Raises:
            ValueError: If item not found or workspace mismatch

        Note:
            This method does NOT commit. The service layer must commit.
        """
        item = self.item_dao.get(session, id=item_id)
        if not item:
            raise ValueError(f"Item {item_id} not found")

        # Validate workspace ownership
        if item.workspace_id != workspace_id:
            raise ValueError(f"Item {item_id} does not belong to workspace {workspace_id}")

        return self.item_dao.remove(session, id=item_id)

    def _assign_tags_to_item(
        self,
        session: Session,
        item_id: int,
        tag_ids: List[int],
        workspace_id: int,
        user_id: int
    ) -> None:
        """
        Assign tags to an item (internal helper method).

        Args:
            session: Database session
            item_id: Item ID
            tag_ids: List of tag IDs to assign
            workspace_id: Workspace ID (for multi-tenancy)
            user_id: User ID performing the assignment

        Note:
            This method does NOT commit. Uses flush for assignments.
        """
        for tag_id in tag_ids:
            # Validate tag exists and belongs to workspace
            tag = item_tag_dao.get(session, id=tag_id)
            if not tag or tag.workspace_id != workspace_id:
                continue  # Skip invalid tags

            # Check if assignment already exists
            if item_tag_assignment_dao.assignment_exists(
                session, item_id=item_id, tag_id=tag_id, workspace_id=workspace_id
            ):
                continue  # Skip if already assigned

            # Create assignment
            assignment_data = {
                'item_id': item_id,
                'tag_id': tag_id,
                'workspace_id': workspace_id,
                'assigned_by': user_id
            }
            item_tag_assignment_dao.create(session, obj_in=assignment_data)

            # Increment tag usage count
            item_tag_dao.increment_usage_count(session, tag_id=tag_id, workspace_id=workspace_id)

    def get_tags_for_item(
        self,
        session: Session,
        item_id: int,
        workspace_id: int
    ) -> List:
        """
        Get all tags assigned to an item.

        Args:
            session: Database session
            item_id: Item ID
            workspace_id: Workspace ID (for multi-tenancy)

        Returns:
            List of ItemTag objects
        """
        return item_tag_assignment_dao.get_tags_for_item(
            session, item_id=item_id, workspace_id=workspace_id
        )


# Singleton instance
item_manager = ItemManager()
