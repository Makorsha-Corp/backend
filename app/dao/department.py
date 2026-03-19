"""DAO operations for Department model

SECURITY NOTICE:
This DAO handles workspace-scoped data. All inherited BaseDAO methods automatically
filter by workspace_id via get_by_workspace() and get_by_id_and_workspace().
"""
from typing import List
from datetime import datetime
from sqlalchemy.orm import Session
from app.dao.base import BaseDAO
from app.models.department import Department
from app.schemas.department import DepartmentCreate, DepartmentUpdate


class DAODepartment(BaseDAO[Department, DepartmentCreate, DepartmentUpdate]):
    """
    DAO operations for Department model (workspace-scoped)

    Uses inherited BaseDAO methods which are workspace-safe:
    - get_by_workspace() - Get all departments in workspace
    - get_by_id_and_workspace() - Get specific department in workspace
    - create_with_workspace() - Create department with workspace_id
    """

    def get_active_departments(
        self, db: Session, *, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[Department]:
        """
        Get all active, non-deleted departments for a workspace (SECURITY-CRITICAL: workspace-filtered)

        Args:
            db: Database session
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of active, non-deleted departments belonging to the workspace
        """
        return (
            db.query(Department)
            .filter(
                Department.workspace_id == workspace_id,  # SECURITY: workspace isolation
                Department.is_active == True,
                Department.is_deleted == False
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def soft_delete(
        self, db: Session, *, db_obj: Department, deleted_by: int
    ) -> Department:
        """
        Soft delete a department (does NOT commit)

        Args:
            db: Database session
            db_obj: Department object to soft delete
            deleted_by: Profile ID of user deleting the department

        Returns:
            Soft-deleted department instance (not yet committed)
        """
        db_obj.is_deleted = True
        db_obj.deleted_at = datetime.utcnow()
        db_obj.deleted_by = deleted_by
        db.add(db_obj)
        db.flush()
        return db_obj

    def restore(
        self, db: Session, *, db_obj: Department
    ) -> Department:
        """
        Restore a soft-deleted department (does NOT commit)

        Args:
            db: Database session
            db_obj: Department object to restore

        Returns:
            Restored department instance (not yet committed)
        """
        db_obj.is_deleted = False
        db_obj.deleted_at = None
        db_obj.deleted_by = None
        db.add(db_obj)
        db.flush()
        return db_obj


department_dao = DAODepartment(Department)
