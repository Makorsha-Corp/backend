"""
Seed default statuses for a workspace

This module provides functionality to create default system statuses
when a new workspace is created.
"""
from sqlalchemy.orm import Session
from app.models.status import Status


DEFAULT_STATUSES = [
    {"name": "Pending", "comment": "Order is pending"},
    {"name": "Office Approved", "comment": "Approved by office"},
    {"name": "Budget Approved", "comment": "Budget has been approved"},
    {"name": "Quotation Requested", "comment": "Quotation has been requested"},
    {"name": "Quotation Received", "comment": "Quotation has been received"},
    {"name": "Purchased", "comment": "Items have been purchased"},
    {"name": "Received", "comment": "Items have been received"},
    {"name": "Completed", "comment": "Order is completed"},
    {"name": "Cancelled", "comment": "Order has been cancelled"},
]


def seed_default_statuses(db: Session, workspace_id: int) -> list[Status]:
    """
    Seed default system statuses for a workspace

    Args:
        db: Database session
        workspace_id: ID of the workspace to seed statuses for

    Returns:
        List of created Status objects

    Note:
        This function does NOT commit the transaction.
        The caller (service layer) is responsible for commit/rollback.
    """
    created_statuses = []

    for status_data in DEFAULT_STATUSES:
        # Check if status already exists (by name in workspace)
        existing_status = (
            db.query(Status)
            .filter(
                Status.workspace_id == workspace_id,
                Status.name == status_data["name"]
            )
            .first()
        )

        if not existing_status:
            status = Status(
                workspace_id=workspace_id,
                name=status_data["name"],
                comment=status_data["comment"]
            )
            db.add(status)
            created_statuses.append(status)

    db.flush()  # Flush to get IDs, but don't commit
    return created_statuses

