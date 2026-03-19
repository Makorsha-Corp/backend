"""
Department Manager

Business logic for department operations.
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.managers.base_manager import BaseManager
from app.models.department import Department
from app.schemas.department import DepartmentCreate, DepartmentUpdate
from app.dao.department import department_dao


class DepartmentManager(BaseManager[Department]):
    """
    Manager for department business logic.

    Handles CRUD operations for departments with workspace isolation.
    """

    def __init__(self):
        super().__init__(Department)
        self.department_dao = department_dao

    def create_department(
        self,
        session: Session,
        department_data: DepartmentCreate,
        workspace_id: int,
        user_id: int
    ) -> Department:
        """
        Create new department.

        Args:
            session: Database session
            department_data: Department creation data
            workspace_id: Workspace ID
            user_id: User creating the department

        Returns:
            Created department

        Raises:
            HTTPException: If department with same name already exists
        """
        # Check if department with same name exists in workspace
        existing_name = self._check_name_exists(
            session, workspace_id=workspace_id, name=department_data.name
        )
        if existing_name:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Department with name '{department_data.name}' already exists"
            )

        # Create department with audit fields
        department_dict = department_data.model_dump()
        department_dict['workspace_id'] = workspace_id
        department_dict['created_by'] = user_id

        department = self.department_dao.create(session, obj_in=department_dict)
        return department

    def update_department(
        self,
        session: Session,
        department_id: int,
        department_data: DepartmentUpdate,
        workspace_id: int,
        user_id: int
    ) -> Department:
        """
        Update department.

        Args:
            session: Database session
            department_id: Department ID
            department_data: Update data
            workspace_id: Workspace ID
            user_id: User updating the department

        Returns:
            Updated department

        Raises:
            HTTPException: If department not found or validation fails
        """
        # Get department
        department = self.department_dao.get_by_id_and_workspace(
            session, id=department_id, workspace_id=workspace_id
        )
        if not department:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Department with ID {department_id} not found"
            )

        # Check if department is deleted
        if department.is_deleted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot update deleted department"
            )

        # Check for name conflicts
        if department_data.name and department_data.name != department.name:
            existing_name = self._check_name_exists(
                session, workspace_id=workspace_id, name=department_data.name, exclude_id=department_id
            )
            if existing_name:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Department with name '{department_data.name}' already exists"
                )

        # Update department with audit fields
        update_dict = department_data.model_dump(exclude_unset=True)
        update_dict['updated_by'] = user_id

        updated_department = self.department_dao.update(session, db_obj=department, obj_in=update_dict)
        return updated_department

    def get_department(
        self,
        session: Session,
        department_id: int,
        workspace_id: int
    ) -> Department:
        """
        Get department by ID.

        Args:
            session: Database session
            department_id: Department ID
            workspace_id: Workspace ID

        Returns:
            Department

        Raises:
            HTTPException: If department not found
        """
        department = self.department_dao.get_by_id_and_workspace(
            session, id=department_id, workspace_id=workspace_id
        )

        if not department:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Department with ID {department_id} not found"
            )

        return department

    def search_departments(
        self,
        session: Session,
        workspace_id: int,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
        include_deleted: bool = False
    ) -> List[Department]:
        """
        Search departments in workspace.

        Args:
            session: Database session
            workspace_id: Workspace ID
            search: Search term (name)
            skip: Number of records to skip
            limit: Maximum number of records to return
            include_deleted: Include soft-deleted departments

        Returns:
            List of departments
        """
        # Get all departments in workspace
        departments = self.department_dao.get_by_workspace(
            session, workspace_id=workspace_id, skip=skip, limit=limit
        )

        # Filter deleted departments unless explicitly requested
        if not include_deleted:
            departments = [d for d in departments if not d.is_deleted]

        # Apply search filter if provided
        if search:
            search_lower = search.lower()
            departments = [
                d for d in departments
                if search_lower in d.name.lower()
            ]

        return departments

    def delete_department(
        self,
        session: Session,
        department_id: int,
        workspace_id: int,
        user_id: int
    ) -> Department:
        """
        Soft delete department.

        Args:
            session: Database session
            department_id: Department ID
            workspace_id: Workspace ID
            user_id: User deleting the department

        Returns:
            Soft-deleted department

        Raises:
            HTTPException: If department not found or already deleted
        """
        department = self.department_dao.get_by_id_and_workspace(
            session, id=department_id, workspace_id=workspace_id
        )

        if not department:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Department with ID {department_id} not found"
            )

        # Check if already deleted
        if department.is_deleted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Department is already deleted"
            )

        # Soft delete
        deleted_department = self.department_dao.soft_delete(session, db_obj=department, deleted_by=user_id)
        return deleted_department

    # ==================== HELPER METHODS ====================

    def _check_name_exists(
        self,
        session: Session,
        workspace_id: int,
        name: str,
        exclude_id: Optional[int] = None
    ) -> bool:
        """
        Check if department with given name exists in workspace (excluding deleted).

        Args:
            session: Database session
            workspace_id: Workspace ID
            name: Department name to check
            exclude_id: Department ID to exclude from check (for updates)

        Returns:
            True if name exists, False otherwise
        """
        departments = self.department_dao.get_by_workspace(session, workspace_id=workspace_id)
        for department in departments:
            # Skip deleted departments
            if department.is_deleted:
                continue
            if department.name == name and (exclude_id is None or department.id != exclude_id):
                return True
        return False


# Singleton instance
department_manager = DepartmentManager()
