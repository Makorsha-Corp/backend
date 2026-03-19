"""Account DAO operations"""
from sqlalchemy.orm import Session
from typing import List, Optional
from app.dao.base import BaseDAO
from app.models.account import Account
from app.models.account_tag_assignment import AccountTagAssignment
from app.models.account_tag import AccountTag
from app.schemas.account import AccountCreate, AccountUpdate


class AccountDAO(BaseDAO[Account, AccountCreate, AccountUpdate]):
    """DAO operations for Account model"""

    def search_by_name_in_workspace(
        self, db: Session, *, workspace_id: int, name: str, skip: int = 0, limit: int = 100
    ) -> List[Account]:
        """
        Search accounts by name within a workspace (SECURITY-CRITICAL)

        Args:
            db: Database session
            workspace_id: Workspace ID to filter by
            name: Account name search query
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of accounts matching the search within workspace
        """
        return (
            db.query(Account)
            .filter(
                Account.workspace_id == workspace_id,
                Account.name.ilike(f"%{name}%"),
                Account.is_active == True,
                Account.is_deleted == False
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_account_code_in_workspace(
        self, db: Session, *, workspace_id: int, account_code: str
    ) -> Optional[Account]:
        """
        Get account by account_code within workspace (SECURITY-CRITICAL)

        Args:
            db: Database session
            workspace_id: Workspace ID to filter by
            account_code: Account code to search for

        Returns:
            Account with matching code or None
        """
        return (
            db.query(Account)
            .filter(
                Account.workspace_id == workspace_id,
                Account.account_code == account_code,
                Account.is_deleted == False
            )
            .first()
        )

    def get_active_accounts_in_workspace(
        self, db: Session, *, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[Account]:
        """
        Get only active accounts within workspace

        Args:
            db: Database session
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of active accounts in workspace
        """
        return (
            db.query(Account)
            .filter(
                Account.workspace_id == workspace_id,
                Account.is_active == True,
                Account.is_deleted == False
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_accounts_in_workspace(
        self,
        db: Session,
        *,
        workspace_id: int,
        name: Optional[str] = None,
        tag_code: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Account]:
        """
        Get accounts in workspace with optional name search and tag filter.

        Args:
            db: Database session
            workspace_id: Workspace ID to filter by
            name: Optional search query for account name
            tag_code: Optional tag_code to filter (e.g. 'supplier', 'client', 'vendor')
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of accounts matching criteria
        """
        query = db.query(Account).filter(
            Account.workspace_id == workspace_id,
            Account.is_active == True,
            Account.is_deleted == False
        )

        if name:
            query = query.filter(Account.name.ilike(f"%{name}%"))

        if tag_code:
            query = (
                query.join(AccountTagAssignment, Account.id == AccountTagAssignment.account_id)
                .join(AccountTag, AccountTagAssignment.tag_id == AccountTag.id)
                .filter(
                    AccountTagAssignment.workspace_id == workspace_id,
                    AccountTag.tag_code == tag_code
                )
            )

        return query.offset(skip).limit(limit).distinct().all()

    def get_accounts_with_invoices_enabled(
        self, db: Session, *, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[Account]:
        """
        Get accounts that have invoices enabled

        Args:
            db: Database session
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of accounts with allow_invoices=True
        """
        return (
            db.query(Account)
            .filter(
                Account.workspace_id == workspace_id,
                Account.allow_invoices == True,
                Account.is_active == True,
                Account.is_deleted == False
            )
            .offset(skip)
            .limit(limit)
            .all()
        )


account_dao = AccountDAO(Account)
