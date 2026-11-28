"""Account DAO operations"""

from sqlalchemy import exists, func
from sqlalchemy.orm import Session

from app.dao.base import BaseDAO
from app.models.account import Account
from app.models.account_tag import AccountTag
from app.models.account_tag_assignment import AccountTagAssignment
from app.schemas.account import AccountCreate, AccountUpdate


class AccountDAO(BaseDAO[Account, AccountCreate, AccountUpdate]):
    """DAO operations for Account model"""

    def search_by_name_in_workspace(
        self, db: Session, *, workspace_id: int, name: str, skip: int = 0, limit: int = 100
    ) -> list[Account]:
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

    def get_accounts_in_workspace(
        self,
        db: Session,
        *,
        workspace_id: int,
        name: str | None = None,
        tag_code: str | None = None,
        skip: int = 0,
        limit: int = 100
    ) -> list[Account]:
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

    def count_active_accounts(self, db: Session, *, workspace_id: int) -> int:
        return (
            db.query(Account)
            .filter(
                Account.workspace_id == workspace_id,
                Account.is_active == True,
                Account.is_deleted == False,
            )
            .count()
        )

    def get_accounts_by_tag_id(
        self,
        db: Session,
        *,
        workspace_id: int,
        tag_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> list[Account]:
        """
        Get all active accounts that have a specific tag assigned (SECURITY-CRITICAL)

        A deleted tag (is_active = False) matches no account. Results are
        ordered by name (case-insensitive), then id, before paging.

        Args:
            db: Database session
            workspace_id: Workspace ID to filter by
            tag_id: Tag ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of accounts tagged with the given tag
        """
        # EXISTS rather than join + DISTINCT: each account appears once, and
        # Postgres refuses ORDER BY lower(name) together with SELECT DISTINCT.
        return (
            db.query(Account)
            .filter(
                Account.workspace_id == workspace_id,
                Account.is_active == True,
                Account.is_deleted == False,
                exists().where(
                    AccountTagAssignment.account_id == Account.id,
                    AccountTagAssignment.workspace_id == workspace_id,
                    AccountTagAssignment.tag_id == tag_id,
                    AccountTag.id == AccountTagAssignment.tag_id,
                    AccountTag.is_active == True,
                ),
            )
            .order_by(func.lower(Account.name).asc(), Account.id.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )

account_dao = AccountDAO(Account)
