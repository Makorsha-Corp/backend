"""Account tag assignment DAO operations"""
from sqlalchemy.orm import Session
from typing import List, Optional
from app.dao.base import BaseDAO
from app.models.account_tag_assignment import AccountTagAssignment
from app.models.account_tag import AccountTag
from app.schemas.account_tag_assignment import AccountTagAssignmentCreate

# Forward declaration to avoid circular import
account_tag_dao = None

def get_account_tag_dao():
    """Lazy import to avoid circular dependency"""
    global account_tag_dao
    if account_tag_dao is None:
        from app.dao.account_tag import account_tag_dao as _dao
        account_tag_dao = _dao
    return account_tag_dao


class AccountTagAssignmentDAO(BaseDAO[AccountTagAssignment, AccountTagAssignmentCreate, AccountTagAssignmentCreate]):
    """DAO operations for AccountTagAssignment model"""

    def get_tags_for_account(
        self, db: Session, *, account_id: int, workspace_id: int
    ) -> List[AccountTag]:
        """
        Get all tags for an account (SECURITY-CRITICAL)

        Args:
            db: Database session
            account_id: Account ID
            workspace_id: Workspace ID to filter by

        Returns:
            List of AccountTag objects assigned to the account
        """
        return (
            db.query(AccountTag)
            .join(AccountTagAssignment, AccountTag.id == AccountTagAssignment.tag_id)
            .filter(
                AccountTagAssignment.workspace_id == workspace_id,
                AccountTagAssignment.account_id == account_id
            )
            .all()
        )

    def get_accounts_for_tag(
        self, db: Session, *, tag_id: int, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[AccountTagAssignment]:
        """
        Get all account assignments for a tag (SECURITY-CRITICAL)

        Args:
            db: Database session
            tag_id: Tag ID
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of account assignments for the tag
        """
        return (
            db.query(AccountTagAssignment)
            .filter(
                AccountTagAssignment.workspace_id == workspace_id,
                AccountTagAssignment.tag_id == tag_id
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_assignment(
        self, db: Session, *, account_id: int, tag_id: int, workspace_id: int
    ) -> Optional[AccountTagAssignment]:
        """
        Get specific tag assignment (SECURITY-CRITICAL)

        Args:
            db: Database session
            account_id: Account ID
            tag_id: Tag ID
            workspace_id: Workspace ID to filter by

        Returns:
            Tag assignment or None
        """
        return (
            db.query(AccountTagAssignment)
            .filter(
                AccountTagAssignment.workspace_id == workspace_id,
                AccountTagAssignment.account_id == account_id,
                AccountTagAssignment.tag_id == tag_id
            )
            .first()
        )

    def assignment_exists(
        self, db: Session, *, account_id: int, tag_id: int, workspace_id: int
    ) -> bool:
        """
        Check if tag assignment exists (SECURITY-CRITICAL)

        Args:
            db: Database session
            account_id: Account ID
            tag_id: Tag ID
            workspace_id: Workspace ID to filter by

        Returns:
            True if assignment exists, False otherwise
        """
        assignment = self.get_assignment(
            db, account_id=account_id, tag_id=tag_id, workspace_id=workspace_id
        )
        return assignment is not None

    def delete_assignment(
        self, db: Session, *, account_id: int, tag_id: int, workspace_id: int
    ) -> bool:
        """
        Delete a tag assignment (SECURITY-CRITICAL)

        Args:
            db: Database session
            account_id: Account ID
            tag_id: Tag ID
            workspace_id: Workspace ID to filter by

        Returns:
            True if deleted, False if not found
        """
        assignment = self.get_assignment(
            db, account_id=account_id, tag_id=tag_id, workspace_id=workspace_id
        )
        if assignment:
            db.delete(assignment)
            db.flush()
            return True
        return False

    def remove_all_tags_from_account(
        self, db: Session, *, account_id: int, workspace_id: int
    ) -> int:
        """
        Remove all tag assignments from an account (SECURITY-CRITICAL)

        Args:
            db: Database session
            account_id: Account ID
            workspace_id: Workspace ID to filter by

        Returns:
            Number of assignments removed
        """
        # Get the actual assignments (not just tags)
        assignments = (
            db.query(AccountTagAssignment)
            .filter(
                AccountTagAssignment.workspace_id == workspace_id,
                AccountTagAssignment.account_id == account_id
            )
            .all()
        )

        tag_dao = get_account_tag_dao()
        count = len(assignments)
        for assignment in assignments:
            # Decrement usage count for each tag
            tag_dao.decrement_usage_count(db, tag_id=assignment.tag_id, workspace_id=workspace_id)
            db.delete(assignment)
        db.flush()
        return count


account_tag_assignment_dao = AccountTagAssignmentDAO(AccountTagAssignment)
