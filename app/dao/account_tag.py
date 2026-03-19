"""Account tag DAO operations"""
from sqlalchemy.orm import Session
from typing import List, Optional
from app.dao.base import BaseDAO
from app.models.account_tag import AccountTag
from app.schemas.account_tag import AccountTagCreate, AccountTagUpdate


class AccountTagDAO(BaseDAO[AccountTag, AccountTagCreate, AccountTagUpdate]):
    """DAO operations for AccountTag model"""

    def get_by_tag_code_in_workspace(
        self, db: Session, *, workspace_id: int, tag_code: str
    ) -> Optional[AccountTag]:
        """
        Get tag by tag_code within workspace (SECURITY-CRITICAL)

        Args:
            db: Database session
            workspace_id: Workspace ID to filter by
            tag_code: Tag code to search for

        Returns:
            AccountTag with matching code or None
        """
        return (
            db.query(AccountTag)
            .filter(
                AccountTag.workspace_id == workspace_id,
                AccountTag.tag_code == tag_code
            )
            .first()
        )

    def get_active_tags_in_workspace(
        self, db: Session, *, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[AccountTag]:
        """
        Get only active tags within workspace

        Args:
            db: Database session
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of active tags in workspace
        """
        return (
            db.query(AccountTag)
            .filter(
                AccountTag.workspace_id == workspace_id,
                AccountTag.is_active == True
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_system_tags_in_workspace(
        self, db: Session, *, workspace_id: int
    ) -> List[AccountTag]:
        """
        Get system tags within workspace

        Args:
            db: Database session
            workspace_id: Workspace ID to filter by

        Returns:
            List of system tags in workspace
        """
        return (
            db.query(AccountTag)
            .filter(
                AccountTag.workspace_id == workspace_id,
                AccountTag.is_system_tag == True
            )
            .all()
        )

    def increment_usage_count(
        self, db: Session, *, tag_id: int, workspace_id: int
    ) -> AccountTag:
        """
        Increment usage count for a tag (SECURITY-CRITICAL)

        Args:
            db: Database session
            tag_id: Tag ID
            workspace_id: Workspace ID to filter by

        Returns:
            Updated tag
        """
        tag = self.get_by_id_and_workspace(db, id=tag_id, workspace_id=workspace_id)
        if tag:
            tag.usage_count += 1
            db.flush()
        return tag

    def decrement_usage_count(
        self, db: Session, *, tag_id: int, workspace_id: int
    ) -> AccountTag:
        """
        Decrement usage count for a tag (SECURITY-CRITICAL)

        Args:
            db: Database session
            tag_id: Tag ID
            workspace_id: Workspace ID to filter by

        Returns:
            Updated tag
        """
        tag = self.get_by_id_and_workspace(db, id=tag_id, workspace_id=workspace_id)
        if tag and tag.usage_count > 0:
            tag.usage_count -= 1
            db.flush()
        return tag


account_tag_dao = AccountTagDAO(AccountTag)
