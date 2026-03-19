"""
Seed default departments for a workspace

This module provides functionality to create default system departments
when a new workspace is created.
"""
from sqlalchemy.orm import Session
from app.models.department import Department


DEFAULT_DEPARTMENTS = [
    {"name": "Production"},
    {"name": "Maintenance"},
    {"name": "Quality Control"},
    {"name": "Warehouse"},
    {"name": "Administration"},
]


def seed_default_departments(db: Session, workspace_id: int) -> list[Department]:
    """
    Seed default system departments for a workspace

    Args:
        db: Database session
        workspace_id: ID of the workspace to seed departments for

    Returns:
        List of created Department objects

    Note:
        This function does NOT commit the transaction.
        The caller (service layer) is responsible for commit/rollback.
    """
    created_departments = []

    for dept_data in DEFAULT_DEPARTMENTS:
        # Check if department already exists (by name in workspace)
        existing_dept = (
            db.query(Department)
            .filter(
                Department.workspace_id == workspace_id,
                Department.name == dept_data["name"]
            )
            .first()
        )

        if not existing_dept:
            department = Department(
                workspace_id=workspace_id,
                name=dept_data["name"]
            )
            db.add(department)
            created_departments.append(department)

    db.flush()  # Flush to get IDs, but don't commit
    return created_departments

