"""
Factory Manager

Business logic for factory operations.
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.managers.base_manager import BaseManager
from app.models.factory import Factory
from app.schemas.factory import FactoryCreate, FactoryUpdate
from app.dao.factory import factory_dao


class FactoryManager(BaseManager[Factory]):
    """
    Manager for factory business logic.

    Handles CRUD operations for factories with workspace isolation.

    Note: Factory model is currently simple (no audit fields or soft delete).
    If these features are needed in future, update Factory model first.
    """

    def __init__(self):
        super().__init__(Factory)
        self.factory_dao = factory_dao

    def create_factory(
        self,
        session: Session,
        factory_data: FactoryCreate,
        workspace_id: int,
        user_id: int
    ) -> Factory:
        """
        Create new factory.

        Args:
            session: Database session
            factory_data: Factory creation data
            workspace_id: Workspace ID
            user_id: User creating the factory

        Returns:
            Created factory

        Raises:
            HTTPException: If factory with same name or abbreviation already exists
        """
        # Check if factory with same name exists in workspace
        existing_name = self._check_name_exists(
            session, workspace_id=workspace_id, name=factory_data.name
        )
        if existing_name:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Factory with name '{factory_data.name}' already exists"
            )

        # Check if factory with same abbreviation exists in workspace
        existing_abbr = self._check_abbreviation_exists(
            session, workspace_id=workspace_id, abbreviation=factory_data.abbreviation
        )
        if existing_abbr:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Factory with abbreviation '{factory_data.abbreviation}' already exists"
            )

        # Create factory with audit fields
        factory_dict = factory_data.model_dump()
        factory_dict['workspace_id'] = workspace_id
        factory_dict['created_by'] = user_id

        factory = self.factory_dao.create(session, obj_in=factory_dict)
        return factory

    def update_factory(
        self,
        session: Session,
        factory_id: int,
        factory_data: FactoryUpdate,
        workspace_id: int,
        user_id: int
    ) -> Factory:
        """
        Update factory.

        Args:
            session: Database session
            factory_id: Factory ID
            factory_data: Update data
            workspace_id: Workspace ID
            user_id: User updating the factory

        Returns:
            Updated factory

        Raises:
            HTTPException: If factory not found or validation fails
        """
        # Get factory
        factory = self.factory_dao.get_by_id_and_workspace(
            session, id=factory_id, workspace_id=workspace_id
        )
        if not factory:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Factory with ID {factory_id} not found"
            )

        # Check if factory is deleted
        if factory.is_deleted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot update deleted factory"
            )

        # Check for name conflicts
        if factory_data.name and factory_data.name != factory.name:
            existing_name = self._check_name_exists(
                session, workspace_id=workspace_id, name=factory_data.name, exclude_id=factory_id
            )
            if existing_name:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Factory with name '{factory_data.name}' already exists"
                )

        # Check for abbreviation conflicts
        if factory_data.abbreviation and factory_data.abbreviation != factory.abbreviation:
            existing_abbr = self._check_abbreviation_exists(
                session, workspace_id=workspace_id, abbreviation=factory_data.abbreviation, exclude_id=factory_id
            )
            if existing_abbr:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Factory with abbreviation '{factory_data.abbreviation}' already exists"
                )

        # Update factory with audit fields
        update_dict = factory_data.model_dump(exclude_unset=True)
        update_dict['updated_by'] = user_id

        updated_factory = self.factory_dao.update(session, db_obj=factory, obj_in=update_dict)
        return updated_factory

    def get_factory(
        self,
        session: Session,
        factory_id: int,
        workspace_id: int
    ) -> Factory:
        """
        Get factory by ID.

        Args:
            session: Database session
            factory_id: Factory ID
            workspace_id: Workspace ID

        Returns:
            Factory

        Raises:
            HTTPException: If factory not found
        """
        factory = self.factory_dao.get_by_id_and_workspace(
            session, id=factory_id, workspace_id=workspace_id
        )

        if not factory:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Factory with ID {factory_id} not found"
            )

        return factory

    def search_factories(
        self,
        session: Session,
        workspace_id: int,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
        include_deleted: bool = False
    ) -> List[Factory]:
        """
        Search factories in workspace.

        Args:
            session: Database session
            workspace_id: Workspace ID
            search: Search term (name or abbreviation)
            skip: Number of records to skip
            limit: Maximum number of records to return
            include_deleted: Include soft-deleted factories

        Returns:
            List of factories
        """
        # Get all factories in workspace
        factories = self.factory_dao.get_by_workspace(
            session, workspace_id=workspace_id, skip=skip, limit=limit
        )

        # Filter deleted factories unless explicitly requested
        if not include_deleted:
            factories = [f for f in factories if not f.is_deleted]

        # Apply search filter if provided
        if search:
            search_lower = search.lower()
            factories = [
                f for f in factories
                if search_lower in f.name.lower() or
                search_lower in f.abbreviation.lower()
            ]

        return factories

    def delete_factory(
        self,
        session: Session,
        factory_id: int,
        workspace_id: int,
        user_id: int
    ) -> Factory:
        """
        Soft delete factory.

        Args:
            session: Database session
            factory_id: Factory ID
            workspace_id: Workspace ID
            user_id: User deleting the factory

        Returns:
            Soft-deleted factory

        Raises:
            HTTPException: If factory not found or already deleted
        """
        factory = self.factory_dao.get_by_id_and_workspace(
            session, id=factory_id, workspace_id=workspace_id
        )

        if not factory:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Factory with ID {factory_id} not found"
            )

        # Check if already deleted
        if factory.is_deleted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Factory is already deleted"
            )

        # Soft delete
        deleted_factory = self.factory_dao.soft_delete(session, db_obj=factory, deleted_by=user_id)
        return deleted_factory

    # ==================== HELPER METHODS ====================

    def _check_name_exists(
        self,
        session: Session,
        workspace_id: int,
        name: str,
        exclude_id: Optional[int] = None
    ) -> bool:
        """
        Check if factory with given name exists in workspace (excluding deleted).

        Args:
            session: Database session
            workspace_id: Workspace ID
            name: Factory name to check
            exclude_id: Factory ID to exclude from check (for updates)

        Returns:
            True if name exists, False otherwise
        """
        factories = self.factory_dao.get_by_workspace(session, workspace_id=workspace_id)
        for factory in factories:
            # Skip deleted factories
            if factory.is_deleted:
                continue
            if factory.name == name and (exclude_id is None or factory.id != exclude_id):
                return True
        return False

    def _check_abbreviation_exists(
        self,
        session: Session,
        workspace_id: int,
        abbreviation: str,
        exclude_id: Optional[int] = None
    ) -> bool:
        """
        Check if factory with given abbreviation exists in workspace (excluding deleted).

        Args:
            session: Database session
            workspace_id: Workspace ID
            abbreviation: Factory abbreviation to check
            exclude_id: Factory ID to exclude from check (for updates)

        Returns:
            True if abbreviation exists, False otherwise
        """
        factories = self.factory_dao.get_by_workspace(session, workspace_id=workspace_id)
        for factory in factories:
            # Skip deleted factories
            if factory.is_deleted:
                continue
            if factory.abbreviation == abbreviation and (exclude_id is None or factory.id != exclude_id):
                return True
        return False


# Singleton instance
factory_manager = FactoryManager()
