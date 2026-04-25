"""Account Service for orchestrating account workflows"""
from typing import List, Optional
from sqlalchemy.orm import Session
from app.services.base_service import BaseService
from app.managers.account_manager import account_manager
from app.models.account import Account
from app.schemas.account import AccountCreate, AccountUpdate, AccountWithTagsResponse
from app.core.exceptions import NotFoundError, BusinessRuleError
from app.dao.account import account_dao
from app.dao.account_tag import account_tag_dao


class AccountService(BaseService):
    """
    Service for Account workflows.

    Handles:
    - Transaction boundaries (commit/rollback)
    - Account CRUD operations
    - Tag management
    - Error handling and exception translation
    """

    def __init__(self):
        super().__init__()
        self.account_manager = account_manager

    def create_account(
        self,
        db: Session,
        account_in: AccountCreate,
        workspace_id: int,
        user_id: int
    ) -> Account:
        """
        Create a new account.

        Args:
            db: Database session
            account_in: Account creation data
            workspace_id: Workspace ID
            user_id: User ID creating the account

        Returns:
            Created account

        Raises:
            ConflictError: If account with same code exists
        """
        try:
            # Create account using manager
            account = self.account_manager.create_account(
                session=db,
                account_data=account_in,
                workspace_id=workspace_id,
                user_id=user_id
            )

            # Commit transaction
            self._commit_transaction(db)
            db.refresh(account)

            return account

        except Exception as e:
            self._rollback_transaction(db)
            raise

    def get_account(
        self,
        db: Session,
        account_id: int,
        workspace_id: int
    ) -> Account:
        """
        Get account by ID.

        Args:
            db: Database session
            account_id: Account ID
            workspace_id: Workspace ID

        Returns:
            Account

        Raises:
            NotFoundError: If account not found
        """
        account = self.account_manager.get_account(db, account_id, workspace_id)
        if not account:
            raise NotFoundError(f"Account with ID {account_id} not found")
        return account

    def get_account_with_tags(
        self,
        db: Session,
        account_id: int,
        workspace_id: int
    ) -> dict:
        """
        Get account by ID with tags included.

        Args:
            db: Database session
            account_id: Account ID
            workspace_id: Workspace ID

        Returns:
            Account dict with tags

        Raises:
            NotFoundError: If account not found
        """
        account = self.account_manager.get_account(db, account_id, workspace_id)
        if not account:
            raise NotFoundError(f"Account with ID {account_id} not found")

        tags = self.account_manager.get_tags_for_account(
            session=db,
            account_id=account.id,
            workspace_id=workspace_id
        )

        return {
            "id": account.id,
            "workspace_id": account.workspace_id,
            "name": account.name,
            "account_code": account.account_code,
            "primary_contact_person": account.primary_contact_person,
            "primary_email": account.primary_email,
            "primary_phone": account.primary_phone,
            "secondary_contact_person": account.secondary_contact_person,
            "secondary_email": account.secondary_email,
            "secondary_phone": account.secondary_phone,
            "address": account.address,
            "city": account.city,
            "country": account.country,
            "postal_code": account.postal_code,
            "payment_preferences": account.payment_preferences,
            "bank_details": account.bank_details,
            "allow_invoices": account.allow_invoices,
            "created_at": account.created_at,
            "account_tags": [
                {
                    "id": tag.id,
                    "name": tag.name,
                    "tag_code": tag.tag_code,
                    "color": tag.color,
                    "icon": tag.icon,
                    "is_system_tag": tag.is_system_tag
                }
                for tag in tags
            ]
        }

    def get_accounts(
        self,
        db: Session,
        workspace_id: int,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Account]:
        """
        Get all accounts with optional search and pagination.

        Args:
            db: Database session
            workspace_id: Workspace ID
            search: Optional search query for account name
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of accounts
        """
        return self.account_manager.search_accounts(
            session=db,
            workspace_id=workspace_id,
            name=search,
            skip=skip,
            limit=limit
        )

    def get_accounts_with_tags(
        self,
        db: Session,
        workspace_id: int,
        search: Optional[str] = None,
        tag_code: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[dict]:
        """
        Get all accounts with their tags included.

        Args:
            db: Database session
            workspace_id: Workspace ID
            search: Optional search query for account name
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of accounts with tags
        """
        accounts = self.account_manager.search_accounts(
            session=db,
            workspace_id=workspace_id,
            name=search,
            tag_code=tag_code,
            skip=skip,
            limit=limit
        )

        # Enrich accounts with tags
        accounts_with_tags = []
        for account in accounts:
            tags = self.account_manager.get_tags_for_account(
                session=db,
                account_id=account.id,
                workspace_id=workspace_id
            )

            account_dict = {
                "id": account.id,
                "workspace_id": account.workspace_id,
                "name": account.name,
                "account_code": account.account_code,
                "primary_contact_person": account.primary_contact_person,
                "primary_email": account.primary_email,
                "primary_phone": account.primary_phone,
                "secondary_contact_person": account.secondary_contact_person,
                "secondary_email": account.secondary_email,
                "secondary_phone": account.secondary_phone,
                "address": account.address,
                "city": account.city,
                "country": account.country,
                "postal_code": account.postal_code,
                "payment_preferences": account.payment_preferences,
                "bank_details": account.bank_details,
                "allow_invoices": account.allow_invoices,
                "created_at": account.created_at,
                "account_tags": [
                    {
                        "id": tag.id,
                        "name": tag.name,
                        "tag_code": tag.tag_code,
                        "color": tag.color,
                        "icon": tag.icon,
                        "is_system_tag": tag.is_system_tag
                    }
                    for tag in tags
                ]
            }
            accounts_with_tags.append(account_dict)

        return accounts_with_tags

    def update_account(
        self,
        db: Session,
        account_id: int,
        account_in: AccountUpdate,
        workspace_id: int,
        user_id: int
    ) -> Account:
        """
        Update an existing account.

        Args:
            db: Database session
            account_id: Account ID
            account_in: Account update data
            workspace_id: Workspace ID
            user_id: User ID updating the account

        Returns:
            Updated account

        Raises:
            NotFoundError: If account not found
        """
        try:
            # Update account using manager
            account = self.account_manager.update_account(
                session=db,
                account_id=account_id,
                account_data=account_in,
                workspace_id=workspace_id,
                user_id=user_id
            )

            if not account:
                raise NotFoundError(f"Account with ID {account_id} not found")

            # Commit transaction
            self._commit_transaction(db)
            db.refresh(account)

            return account

        except NotFoundError:
            self._rollback_transaction(db)
            raise
        except Exception as e:
            self._rollback_transaction(db)
            raise

    def get_accounts_by_tag_id(
        self,
        db: Session,
        tag_id: int,
        workspace_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[dict]:
        """
        Get all accounts that have a specific tag assigned.

        Raises:
            NotFoundError: If the tag does not exist in the workspace
        """
        tag = account_tag_dao.get_by_id_and_workspace(db, id=tag_id, workspace_id=workspace_id)
        if not tag:
            raise NotFoundError(f"Account tag {tag_id} not found")

        accounts = account_dao.get_accounts_by_tag_id(
            db, workspace_id=workspace_id, tag_id=tag_id, skip=skip, limit=limit
        )

        result = []
        for account in accounts:
            tags = self.account_manager.get_tags_for_account(
                session=db, account_id=account.id, workspace_id=workspace_id
            )
            result.append({
                "id": account.id,
                "workspace_id": account.workspace_id,
                "name": account.name,
                "account_code": account.account_code,
                "primary_contact_person": account.primary_contact_person,
                "primary_email": account.primary_email,
                "primary_phone": account.primary_phone,
                "secondary_contact_person": account.secondary_contact_person,
                "secondary_email": account.secondary_email,
                "secondary_phone": account.secondary_phone,
                "address": account.address,
                "city": account.city,
                "country": account.country,
                "postal_code": account.postal_code,
                "payment_preferences": account.payment_preferences,
                "bank_details": account.bank_details,
                "allow_invoices": account.allow_invoices,
                "created_at": account.created_at,
                "account_tags": [
                    {
                        "id": t.id,
                        "name": t.name,
                        "tag_code": t.tag_code,
                        "color": t.color,
                        "icon": t.icon,
                        "is_system_tag": t.is_system_tag
                    }
                    for t in tags
                ]
            })
        return result

    def assign_tag(
        self,
        db: Session,
        account_id: int,
        tag_id: int,
        workspace_id: int,
        user_id: int
    ) -> dict:
        """Assign a tag to an account. Returns updated account with tags."""
        try:
            self.account_manager.assign_tag(
                session=db,
                account_id=account_id,
                tag_id=tag_id,
                workspace_id=workspace_id,
                user_id=user_id
            )
            self._commit_transaction(db)
            return self.get_account_with_tags(db, account_id, workspace_id=workspace_id)
        except ValueError as e:
            self._rollback_transaction(db)
            error_msg = str(e)
            if "not found" in error_msg:
                raise NotFoundError(error_msg)
            raise BusinessRuleError(error_msg)
        except Exception:
            self._rollback_transaction(db)
            raise

    def unassign_tag(
        self,
        db: Session,
        account_id: int,
        tag_id: int,
        workspace_id: int
    ) -> None:
        """Remove a tag from an account."""
        try:
            self.account_manager.unassign_tag(
                session=db,
                account_id=account_id,
                tag_id=tag_id,
                workspace_id=workspace_id
            )
            self._commit_transaction(db)
        except ValueError as e:
            self._rollback_transaction(db)
            error_msg = str(e)
            if "not found" in error_msg:
                raise NotFoundError(error_msg)
            raise BusinessRuleError(error_msg)
        except Exception:
            self._rollback_transaction(db)
            raise

    def delete_account(
        self,
        db: Session,
        account_id: int,
        workspace_id: int,
        user_id: int
    ) -> None:
        """
        Delete an account (soft delete).

        Args:
            db: Database session
            account_id: Account ID
            workspace_id: Workspace ID
            user_id: User ID deleting the account

        Raises:
            NotFoundError: If account not found
        """
        try:
            # Check if account exists
            account = self.account_manager.get_account(db, account_id, workspace_id)
            if not account:
                raise NotFoundError(f"Account with ID {account_id} not found")

            # Delete account using manager
            self.account_manager.delete_account(
                session=db,
                account_id=account_id,
                workspace_id=workspace_id,
                user_id=user_id
            )

            # Commit transaction
            self._commit_transaction(db)

        except NotFoundError:
            self._rollback_transaction(db)
            raise
        except Exception as e:
            self._rollback_transaction(db)
            raise


# Singleton instance
account_service = AccountService()
