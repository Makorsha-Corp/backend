"""Account Manager for account business logic"""
from typing import List, Optional
from sqlalchemy.orm import Session
from app.managers.base_manager import BaseManager
from app.models.account import Account
from app.dao.account import account_dao
from app.dao.account_tag import account_tag_dao
from app.dao.account_tag_assignment import account_tag_assignment_dao
from app.schemas.account import AccountCreate, AccountUpdate
from app.utils.audit_logger import log_financial_audit, create_change_dict, extract_relevant_fields


class AccountManager(BaseManager[Account]):
    """
    STANDALONE MANAGER: Account operations with tag support.

    Manages: Account entity with tag assignments

    Operations: CRUD, search, tag management

    Does NOT commit transactions - that's the service layer's responsibility.
    """

    def __init__(self):
        super().__init__(Account)
        self.account_dao = account_dao

    def create_account(
        self,
        session: Session,
        account_data: AccountCreate,
        workspace_id: int,
        user_id: int
    ) -> Account:
        """
        Create a new account with tag assignments.

        Args:
            session: Database session
            account_data: Account creation data (including tag_ids)
            workspace_id: Workspace ID (for multi-tenancy)
            user_id: User ID creating the account (for audit)

        Returns:
            Created account (not yet committed)

        Note:
            This method does NOT commit. The service layer must commit.
        """
        # Extract tag_ids before creating account
        tag_ids = account_data.tag_ids if hasattr(account_data, 'tag_ids') else []

        # Convert Pydantic model to dict and inject workspace/audit fields
        account_dict = account_data.model_dump(exclude={'tag_ids'})
        account_dict['workspace_id'] = workspace_id
        account_dict['created_by'] = user_id

        # Create the account
        account = self.account_dao.create(session, obj_in=account_dict)

        # Assign tags if provided
        if tag_ids:
            self._assign_tags_to_account(
                session=session,
                account_id=account.id,
                tag_ids=tag_ids,
                workspace_id=workspace_id,
                user_id=user_id
            )

        # Audit log
        log_financial_audit(
            session=session,
            workspace_id=workspace_id,
            entity_type='account',
            entity_id=account.id,
            action_type='created',
            performed_by=user_id,
            changes=create_change_dict(after=extract_relevant_fields(
                account, ['name', 'primary_email', 'primary_phone', 'address_line1']
            )),
            description=f"Account '{account.name}' created"
        )

        return account

    def update_account(
        self,
        session: Session,
        account_id: int,
        account_data: AccountUpdate,
        workspace_id: int,
        user_id: int
    ) -> Account:
        """
        Update an existing account with optional tag updates.

        Args:
            session: Database session
            account_id: Account ID
            account_data: Account update data (including optional tag_ids)
            workspace_id: Workspace ID (for multi-tenancy)
            user_id: User ID updating the account (for audit)

        Returns:
            Updated account (not yet committed)

        Raises:
            ValueError: If account not found or workspace mismatch

        Note:
            This method does NOT commit. The service layer must commit.
        """
        account = self.account_dao.get(session, id=account_id)
        if not account:
            raise ValueError(f"Account {account_id} not found")

        # Validate workspace ownership
        if account.workspace_id != workspace_id:
            raise ValueError(f"Account {account_id} does not belong to workspace {workspace_id}")

        # Capture before state for audit
        before_state = extract_relevant_fields(
            account, ['name', 'primary_email', 'primary_phone', 'address_line1', 'is_active']
        )

        # Extract tag_ids if provided
        tag_ids = None
        if hasattr(account_data, 'tag_ids') and account_data.tag_ids is not None:
            tag_ids = account_data.tag_ids

        # Inject updated_by for audit
        account_dict = account_data.model_dump(exclude_unset=True, exclude={'tag_ids'})
        account_dict['updated_by'] = user_id

        # Update the account
        updated_account = self.account_dao.update(session, db_obj=account, obj_in=account_dict)

        # Update tags if provided
        if tag_ids is not None:
            # Remove all existing tags
            account_tag_assignment_dao.remove_all_tags_from_account(
                session, account_id=account_id, workspace_id=workspace_id
            )
            # Assign new tags
            if tag_ids:
                self._assign_tags_to_account(
                    session=session,
                    account_id=account_id,
                    tag_ids=tag_ids,
                    workspace_id=workspace_id,
                    user_id=user_id
                )

        # Capture after state for audit
        after_state = extract_relevant_fields(
            updated_account, ['name', 'primary_email', 'primary_phone', 'address_line1', 'is_active']
        )

        # Audit log
        log_financial_audit(
            session=session,
            workspace_id=workspace_id,
            entity_type='account',
            entity_id=account.id,
            action_type='updated',
            performed_by=user_id,
            changes=create_change_dict(before=before_state, after=after_state),
            description=f"Account '{account.name}' updated"
        )

        return updated_account

    def get_account(
        self,
        session: Session,
        account_id: int,
        workspace_id: int
    ) -> Optional[Account]:
        """
        Get account by ID within workspace.

        Args:
            session: Database session
            account_id: Account ID
            workspace_id: Workspace ID (for multi-tenancy)

        Returns:
            Account or None if not found or not in workspace

        Note:
            Returns None if account exists but doesn't belong to workspace (security)
        """
        account = self.account_dao.get(session, id=account_id)
        if account and account.workspace_id != workspace_id:
            # Account exists but not in this workspace - don't leak existence
            return None
        return account

    def search_accounts(
        self,
        session: Session,
        workspace_id: int,
        name: Optional[str] = None,
        tag_code: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Account]:
        """
        Search accounts by name and/or tag within workspace.

        Args:
            session: Database session
            workspace_id: Workspace ID (for multi-tenancy)
            name: Optional search query for account name
            tag_code: Optional tag code to filter (e.g. 'supplier', 'client', 'vendor')
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of accounts in workspace
        """
        return self.account_dao.get_accounts_in_workspace(
            session,
            workspace_id=workspace_id,
            name=name,
            tag_code=tag_code,
            skip=skip,
            limit=limit
        )

    def delete_account(
        self,
        session: Session,
        account_id: int,
        workspace_id: int
    ) -> Account:
        """
        Delete an account (soft delete).

        Args:
            session: Database session
            account_id: Account ID
            workspace_id: Workspace ID (for multi-tenancy)

        Returns:
            Deleted account (not yet committed)

        Raises:
            ValueError: If account not found or workspace mismatch

        Note:
            This method does NOT commit. The service layer must commit.
        """
        account = self.account_dao.get(session, id=account_id)
        if not account:
            raise ValueError(f"Account {account_id} not found")

        # Validate workspace ownership
        if account.workspace_id != workspace_id:
            raise ValueError(f"Account {account_id} does not belong to workspace {workspace_id}")

        # Audit log before deletion
        log_financial_audit(
            session=session,
            workspace_id=workspace_id,
            entity_type='account',
            entity_id=account.id,
            action_type='deleted',
            performed_by=0,  # No user_id passed to delete method currently
            changes=create_change_dict(before=extract_relevant_fields(
                account, ['name', 'primary_email', 'primary_phone']
            )),
            description=f"Account '{account.name}' deleted"
        )

        return self.account_dao.remove(session, id=account_id)

    def _assign_tags_to_account(
        self,
        session: Session,
        account_id: int,
        tag_ids: List[int],
        workspace_id: int,
        user_id: int
    ) -> None:
        """
        Assign tags to an account (internal helper method).

        Args:
            session: Database session
            account_id: Account ID
            tag_ids: List of tag IDs to assign
            workspace_id: Workspace ID (for multi-tenancy)
            user_id: User ID performing the assignment

        Note:
            This method does NOT commit. Uses flush for assignments.
        """
        for tag_id in tag_ids:
            # Validate tag exists and belongs to workspace
            tag = account_tag_dao.get_by_id_and_workspace(session, id=tag_id, workspace_id=workspace_id)
            if not tag:
                continue  # Skip invalid tags

            # Check if assignment already exists
            if account_tag_assignment_dao.assignment_exists(
                session, account_id=account_id, tag_id=tag_id, workspace_id=workspace_id
            ):
                continue  # Skip if already assigned

            # Create assignment
            assignment_data = {
                'account_id': account_id,
                'tag_id': tag_id,
                'workspace_id': workspace_id,
                'assigned_by': user_id
            }
            account_tag_assignment_dao.create(session, obj_in=assignment_data)

            # Increment tag usage count
            account_tag_dao.increment_usage_count(session, tag_id=tag_id, workspace_id=workspace_id)

    def get_tags_for_account(
        self,
        session: Session,
        account_id: int,
        workspace_id: int
    ) -> List:
        """
        Get all tags assigned to an account.

        Args:
            session: Database session
            account_id: Account ID
            workspace_id: Workspace ID (for multi-tenancy)

        Returns:
            List of AccountTag objects
        """
        return account_tag_assignment_dao.get_tags_for_account(
            session, account_id=account_id, workspace_id=workspace_id
        )


# Singleton instance
account_manager = AccountManager()
