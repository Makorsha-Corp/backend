"""Factory Section Service for orchestrating factory section workflows"""
from typing import List, Optional
from sqlalchemy.orm import Session

from app.services.base_service import BaseService
from app.managers.factory_section_manager import factory_section_manager
from app.models.factory_section import FactorySection
from app.schemas.factory_section import FactorySectionCreate, FactorySectionUpdate


class FactorySectionService(BaseService):
    """
    Service for Factory Section workflows.

    Handles:
    - Transaction boundaries (commit/rollback)
    - Factory section CRUD operations
    - Factory relationship validation
    - Error handling and exception translation
    """

    def __init__(self):
        super().__init__()
        self.factory_section_manager = factory_section_manager

    def create_factory_section(
        self,
        db: Session,
        section_in: FactorySectionCreate,
        workspace_id: int,
        user_id: int
    ) -> FactorySection:
        """
        Create a new factory section.

        Args:
            db: Database session
            section_in: Factory section creation data
            workspace_id: Workspace ID
            user_id: User creating the section

        Returns:
            Created factory section

        Raises:
            HTTPException: If factory not found or section name exists
        """
        try:
            # Create factory section using manager
            section = self.factory_section_manager.create_factory_section(
                session=db,
                section_data=section_in,
                workspace_id=workspace_id,
                user_id=user_id
            )

            # Commit transaction
            self._commit_transaction(db)
            db.refresh(section)

            return section

        except Exception as e:
            self._rollback_transaction(db)
            raise

    def get_factory_section(
        self,
        db: Session,
        section_id: int,
        workspace_id: int
    ) -> FactorySection:
        """
        Get factory section by ID.

        Args:
            db: Database session
            section_id: Factory section ID
            workspace_id: Workspace ID

        Returns:
            Factory section

        Raises:
            HTTPException: If section not found
        """
        return self.factory_section_manager.get_factory_section(db, section_id, workspace_id)

    def get_factory_sections(
        self,
        db: Session,
        workspace_id: int,
        factory_id: Optional[int] = None,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[FactorySection]:
        """
        Get factory sections in workspace.

        Args:
            db: Database session
            workspace_id: Workspace ID
            factory_id: Filter by factory ID (optional)
            search: Search term (optional)
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of factory sections
        """
        return self.factory_section_manager.search_factory_sections(
            session=db,
            workspace_id=workspace_id,
            factory_id=factory_id,
            search=search,
            skip=skip,
            limit=limit
        )

    def update_factory_section(
        self,
        db: Session,
        section_id: int,
        section_in: FactorySectionUpdate,
        workspace_id: int,
        user_id: int
    ) -> FactorySection:
        """
        Update factory section.

        Args:
            db: Database session
            section_id: Factory section ID
            section_in: Update data
            workspace_id: Workspace ID
            user_id: User updating the section

        Returns:
            Updated factory section

        Raises:
            HTTPException: If section not found or validation fails
        """
        try:
            # Update factory section using manager
            section = self.factory_section_manager.update_factory_section(
                session=db,
                section_id=section_id,
                section_data=section_in,
                workspace_id=workspace_id,
                user_id=user_id
            )

            # Commit transaction
            self._commit_transaction(db)
            db.refresh(section)

            return section

        except Exception as e:
            self._rollback_transaction(db)
            raise

    def delete_factory_section(
        self,
        db: Session,
        section_id: int,
        workspace_id: int,
        user_id: int
    ) -> FactorySection:
        """
        Soft delete factory section.

        Args:
            db: Database session
            section_id: Factory section ID
            workspace_id: Workspace ID
            user_id: User deleting the section

        Returns:
            Soft-deleted factory section

        Raises:
            HTTPException: If section not found or already deleted
        """
        try:
            # Soft delete factory section using manager
            section = self.factory_section_manager.delete_factory_section(
                session=db,
                section_id=section_id,
                workspace_id=workspace_id,
                user_id=user_id
            )

            # Commit transaction
            self._commit_transaction(db)
            db.refresh(section)

            return section

        except Exception as e:
            self._rollback_transaction(db)
            raise


# Singleton instance
factory_section_service = FactorySectionService()
