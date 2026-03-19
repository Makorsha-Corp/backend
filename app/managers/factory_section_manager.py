"""
Factory Section Manager

Business logic for factory section operations.
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.managers.base_manager import BaseManager
from app.models.factory_section import FactorySection
from app.schemas.factory_section import FactorySectionCreate, FactorySectionUpdate
from app.dao.factory_section import factory_section_dao
from app.dao.factory import factory_dao


class FactorySectionManager(BaseManager[FactorySection]):
    """
    Manager for factory section business logic.

    Handles CRUD operations for factory sections with workspace isolation
    and factory relationship validation.
    """

    def __init__(self):
        super().__init__(FactorySection)
        self.factory_section_dao = factory_section_dao
        self.factory_dao = factory_dao

    def create_factory_section(
        self,
        session: Session,
        section_data: FactorySectionCreate,
        workspace_id: int,
        user_id: int
    ) -> FactorySection:
        """
        Create new factory section.

        Args:
            session: Database session
            section_data: Factory section creation data
            workspace_id: Workspace ID
            user_id: User creating the section

        Returns:
            Created factory section

        Raises:
            HTTPException: If factory not found or section name already exists in factory
        """
        # Validate factory exists and belongs to workspace
        factory = self.factory_dao.get_by_id_and_workspace(
            session, id=section_data.factory_id, workspace_id=workspace_id
        )
        if not factory:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Factory with ID {section_data.factory_id} not found"
            )

        # Check if factory is deleted
        if factory.is_deleted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot create section for deleted factory"
            )

        # Check if section with same name exists in this factory
        existing = self._check_name_exists_in_factory(
            session,
            workspace_id=workspace_id,
            factory_id=section_data.factory_id,
            name=section_data.name
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Section with name '{section_data.name}' already exists in this factory"
            )

        # Create factory section with audit fields
        section_dict = section_data.model_dump()
        section_dict['workspace_id'] = workspace_id
        section_dict['created_by'] = user_id

        section = self.factory_section_dao.create(session, obj_in=section_dict)
        return section

    def update_factory_section(
        self,
        session: Session,
        section_id: int,
        section_data: FactorySectionUpdate,
        workspace_id: int,
        user_id: int
    ) -> FactorySection:
        """
        Update factory section.

        Args:
            session: Database session
            section_id: Factory section ID
            section_data: Update data
            workspace_id: Workspace ID
            user_id: User updating the section

        Returns:
            Updated factory section

        Raises:
            HTTPException: If section not found or validation fails
        """
        # Get factory section
        section = self.factory_section_dao.get_by_id_and_workspace(
            session, id=section_id, workspace_id=workspace_id
        )
        if not section:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Factory section with ID {section_id} not found"
            )

        # Check if section is deleted
        if section.is_deleted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot update deleted factory section"
            )

        # If factory_id is being changed, validate new factory
        if section_data.factory_id and section_data.factory_id != section.factory_id:
            factory = self.factory_dao.get_by_id_and_workspace(
                session, id=section_data.factory_id, workspace_id=workspace_id
            )
            if not factory:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Factory with ID {section_data.factory_id} not found"
                )
            # Check if new factory is deleted
            if factory.is_deleted:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot move section to deleted factory"
                )

        # Check for name conflicts in the target factory
        target_factory_id = section_data.factory_id if section_data.factory_id else section.factory_id
        if section_data.name and section_data.name != section.name:
            existing = self._check_name_exists_in_factory(
                session,
                workspace_id=workspace_id,
                factory_id=target_factory_id,
                name=section_data.name,
                exclude_id=section_id
            )
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Section with name '{section_data.name}' already exists in this factory"
                )

        # Update factory section with audit fields
        update_dict = section_data.model_dump(exclude_unset=True)
        update_dict['updated_by'] = user_id

        updated_section = self.factory_section_dao.update(session, db_obj=section, obj_in=update_dict)
        return updated_section

    def get_factory_section(
        self,
        session: Session,
        section_id: int,
        workspace_id: int
    ) -> FactorySection:
        """
        Get factory section by ID.

        Args:
            session: Database session
            section_id: Factory section ID
            workspace_id: Workspace ID

        Returns:
            Factory section

        Raises:
            HTTPException: If section not found
        """
        section = self.factory_section_dao.get_by_id_and_workspace(
            session, id=section_id, workspace_id=workspace_id
        )

        if not section:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Factory section with ID {section_id} not found"
            )

        return section

    def search_factory_sections(
        self,
        session: Session,
        workspace_id: int,
        factory_id: Optional[int] = None,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
        include_deleted: bool = False
    ) -> List[FactorySection]:
        """
        Search factory sections in workspace.

        Args:
            session: Database session
            workspace_id: Workspace ID
            factory_id: Filter by factory ID (optional)
            search: Search term (name)
            skip: Number of records to skip
            limit: Maximum number of records to return
            include_deleted: Include soft-deleted sections

        Returns:
            List of factory sections
        """
        if factory_id:
            # Get sections for specific factory
            sections = self.factory_section_dao.get_by_factory(
                session, factory_id=factory_id, workspace_id=workspace_id, skip=skip, limit=limit
            )
        else:
            # Get all sections in workspace
            sections = self.factory_section_dao.get_by_workspace(
                session, workspace_id=workspace_id, skip=skip, limit=limit
            )

        # Filter deleted sections unless explicitly requested
        if not include_deleted:
            sections = [s for s in sections if not s.is_deleted]

        # Apply search filter if provided
        if search:
            search_lower = search.lower()
            sections = [
                s for s in sections
                if search_lower in s.name.lower()
            ]

        return sections

    def delete_factory_section(
        self,
        session: Session,
        section_id: int,
        workspace_id: int,
        user_id: int
    ) -> FactorySection:
        """
        Soft delete factory section.

        Args:
            session: Database session
            section_id: Factory section ID
            workspace_id: Workspace ID
            user_id: User deleting the section

        Returns:
            Soft-deleted factory section

        Raises:
            HTTPException: If section not found or already deleted
        """
        section = self.factory_section_dao.get_by_id_and_workspace(
            session, id=section_id, workspace_id=workspace_id
        )

        if not section:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Factory section with ID {section_id} not found"
            )

        # Check if already deleted
        if section.is_deleted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Factory section is already deleted"
            )

        # Soft delete
        deleted_section = self.factory_section_dao.soft_delete(session, db_obj=section, deleted_by=user_id)
        return deleted_section

    # ==================== HELPER METHODS ====================

    def _check_name_exists_in_factory(
        self,
        session: Session,
        workspace_id: int,
        factory_id: int,
        name: str,
        exclude_id: Optional[int] = None
    ) -> bool:
        """
        Check if section with given name exists in factory (excluding deleted).

        Args:
            session: Database session
            workspace_id: Workspace ID
            factory_id: Factory ID
            name: Section name to check
            exclude_id: Section ID to exclude from check (for updates)

        Returns:
            True if name exists, False otherwise
        """
        sections = self.factory_section_dao.get_by_factory(
            session, factory_id=factory_id, workspace_id=workspace_id
        )
        for section in sections:
            # Skip deleted sections
            if section.is_deleted:
                continue
            if section.name == name and (exclude_id is None or section.id != exclude_id):
                return True
        return False


# Singleton instance
factory_section_manager = FactorySectionManager()
