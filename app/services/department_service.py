"""Department Service for orchestrating department workflows"""
from typing import List, Optional
from sqlalchemy.orm import Session

from app.services.base_service import BaseService
from app.managers.department_manager import department_manager
from app.models.department import Department
from app.schemas.department import DepartmentCreate, DepartmentUpdate


class DepartmentService(BaseService):
    """
    Service for Department workflows.

    Handles:
    - Transaction boundaries (commit/rollback)
    - Department CRUD operations
    - Error handling and exception translation
    """

    def __init__(self):
        super().__init__()
        self.department_manager = department_manager

    def create_department(
        self,
        db: Session,
        department_in: DepartmentCreate,
        workspace_id: int,
        user_id: int
    ) -> Department:
        """
        Create a new department.

        Args:
            db: Database session
            department_in: Department creation data
            workspace_id: Workspace ID
            user_id: User creating the department

        Returns:
            Created department

        Raises:
            HTTPException: If department with same name exists
        """
        try:
            # Create department using manager
            department = self.department_manager.create_department(
                session=db,
                department_data=department_in,
                workspace_id=workspace_id,
                user_id=user_id
            )

            # Commit transaction
            self._commit_transaction(db)
            db.refresh(department)

            return department

        except Exception as e:
            self._rollback_transaction(db)
            raise

    def get_department(
        self,
        db: Session,
        department_id: int,
        workspace_id: int
    ) -> Department:
        """
        Get department by ID.

        Args:
            db: Database session
            department_id: Department ID
            workspace_id: Workspace ID

        Returns:
            Department

        Raises:
            HTTPException: If department not found
        """
        return self.department_manager.get_department(db, department_id, workspace_id)

    def get_departments(
        self,
        db: Session,
        workspace_id: int,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Department]:
        """
        Get departments in workspace.

        Args:
            db: Database session
            workspace_id: Workspace ID
            search: Search term (optional)
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of departments
        """
        return self.department_manager.search_departments(
            session=db,
            workspace_id=workspace_id,
            search=search,
            skip=skip,
            limit=limit
        )

    def update_department(
        self,
        db: Session,
        department_id: int,
        department_in: DepartmentUpdate,
        workspace_id: int,
        user_id: int
    ) -> Department:
        """
        Update department.

        Args:
            db: Database session
            department_id: Department ID
            department_in: Update data
            workspace_id: Workspace ID
            user_id: User updating the department

        Returns:
            Updated department

        Raises:
            HTTPException: If department not found or validation fails
        """
        try:
            # Update department using manager
            department = self.department_manager.update_department(
                session=db,
                department_id=department_id,
                department_data=department_in,
                workspace_id=workspace_id,
                user_id=user_id
            )

            # Commit transaction
            self._commit_transaction(db)
            db.refresh(department)

            return department

        except Exception as e:
            self._rollback_transaction(db)
            raise

    def delete_department(
        self,
        db: Session,
        department_id: int,
        workspace_id: int,
        user_id: int
    ) -> Department:
        """
        Soft delete department.

        Args:
            db: Database session
            department_id: Department ID
            workspace_id: Workspace ID
            user_id: User deleting the department

        Returns:
            Soft-deleted department

        Raises:
            HTTPException: If department not found or already deleted
        """
        try:
            # Soft delete department using manager
            department = self.department_manager.delete_department(
                session=db,
                department_id=department_id,
                workspace_id=workspace_id,
                user_id=user_id
            )

            # Commit transaction
            self._commit_transaction(db)
            db.refresh(department)

            return department

        except Exception as e:
            self._rollback_transaction(db)
            raise


# Singleton instance
department_service = DepartmentService()
