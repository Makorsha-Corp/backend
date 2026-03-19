"""Factory Service for orchestrating factory workflows"""
from typing import List, Optional
from sqlalchemy.orm import Session

from app.services.base_service import BaseService
from app.managers.factory_manager import factory_manager
from app.models.factory import Factory
from app.schemas.factory import FactoryCreate, FactoryUpdate


class FactoryService(BaseService):
    """
    Service for Factory workflows.

    Handles:
    - Transaction boundaries (commit/rollback)
    - Factory CRUD operations
    - Error handling and exception translation
    """

    def __init__(self):
        super().__init__()
        self.factory_manager = factory_manager

    def create_factory(
        self,
        db: Session,
        factory_in: FactoryCreate,
        workspace_id: int,
        user_id: int
    ) -> Factory:
        """
        Create a new factory.

        Args:
            db: Database session
            factory_in: Factory creation data
            workspace_id: Workspace ID
            user_id: User creating the factory

        Returns:
            Created factory

        Raises:
            HTTPException: If factory with same name or abbreviation exists
        """
        try:
            # Create factory using manager
            factory = self.factory_manager.create_factory(
                session=db,
                factory_data=factory_in,
                workspace_id=workspace_id,
                user_id=user_id
            )

            # Commit transaction
            self._commit_transaction(db)
            db.refresh(factory)

            return factory

        except Exception as e:
            self._rollback_transaction(db)
            raise

    def get_factory(
        self,
        db: Session,
        factory_id: int,
        workspace_id: int
    ) -> Factory:
        """
        Get factory by ID.

        Args:
            db: Database session
            factory_id: Factory ID
            workspace_id: Workspace ID

        Returns:
            Factory

        Raises:
            HTTPException: If factory not found
        """
        return self.factory_manager.get_factory(db, factory_id, workspace_id)

    def get_factories(
        self,
        db: Session,
        workspace_id: int,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Factory]:
        """
        Get factories in workspace.

        Args:
            db: Database session
            workspace_id: Workspace ID
            search: Search term (optional)
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of factories
        """
        return self.factory_manager.search_factories(
            session=db,
            workspace_id=workspace_id,
            search=search,
            skip=skip,
            limit=limit
        )

    def update_factory(
        self,
        db: Session,
        factory_id: int,
        factory_in: FactoryUpdate,
        workspace_id: int,
        user_id: int
    ) -> Factory:
        """
        Update factory.

        Args:
            db: Database session
            factory_id: Factory ID
            factory_in: Update data
            workspace_id: Workspace ID
            user_id: User updating the factory

        Returns:
            Updated factory

        Raises:
            HTTPException: If factory not found or validation fails
        """
        try:
            # Update factory using manager
            factory = self.factory_manager.update_factory(
                session=db,
                factory_id=factory_id,
                factory_data=factory_in,
                workspace_id=workspace_id,
                user_id=user_id
            )

            # Commit transaction
            self._commit_transaction(db)
            db.refresh(factory)

            return factory

        except Exception as e:
            self._rollback_transaction(db)
            raise

    def delete_factory(
        self,
        db: Session,
        factory_id: int,
        workspace_id: int,
        user_id: int
    ) -> Factory:
        """
        Soft delete factory.

        Args:
            db: Database session
            factory_id: Factory ID
            workspace_id: Workspace ID
            user_id: User deleting the factory

        Returns:
            Soft-deleted factory

        Raises:
            HTTPException: If factory not found or already deleted
        """
        try:
            # Soft delete factory using manager
            factory = self.factory_manager.delete_factory(
                session=db,
                factory_id=factory_id,
                workspace_id=workspace_id,
                user_id=user_id
            )

            # Commit transaction
            self._commit_transaction(db)
            db.refresh(factory)

            return factory

        except Exception as e:
            self._rollback_transaction(db)
            raise


# Singleton instance
factory_service = FactoryService()
