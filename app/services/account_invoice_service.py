"""Account Invoice Service for orchestrating invoice workflows"""
from typing import List, Optional
from sqlalchemy.orm import Session

from app.services.base_service import BaseService
from app.managers.account_invoice_manager import account_invoice_manager
from app.models.account_invoice import AccountInvoice
from app.schemas.account_invoice import AccountInvoiceCreate, AccountInvoiceUpdate


class AccountInvoiceService(BaseService):
    """
    Service for Account Invoice workflows.

    Handles:
    - Transaction boundaries (commit/rollback)
    - Invoice CRUD operations
    - Error handling and exception translation
    """

    def __init__(self):
        super().__init__()
        self.account_invoice_manager = account_invoice_manager

    def create_invoice(
        self,
        db: Session,
        invoice_in: AccountInvoiceCreate,
        workspace_id: int,
        user_id: int
    ) -> AccountInvoice:
        """
        Create a new invoice.

        Args:
            db: Database session
            invoice_in: Invoice creation data
            workspace_id: Workspace ID
            user_id: User creating the invoice

        Returns:
            Created invoice

        Raises:
            HTTPException: If account not found or validation fails
        """
        try:
            # Create invoice using manager
            invoice = self.account_invoice_manager.create_invoice(
                session=db,
                invoice_data=invoice_in,
                workspace_id=workspace_id,
                user_id=user_id
            )

            # Commit transaction
            self._commit_transaction(db)
            db.refresh(invoice)

            return invoice

        except Exception as e:
            self._rollback_transaction(db)
            raise

    def get_invoice(
        self,
        db: Session,
        invoice_id: int,
        workspace_id: int
    ) -> AccountInvoice:
        """
        Get invoice by ID.

        Args:
            db: Database session
            invoice_id: Invoice ID
            workspace_id: Workspace ID

        Returns:
            Invoice

        Raises:
            HTTPException: If invoice not found
        """
        return self.account_invoice_manager.get_invoice(db, invoice_id, workspace_id)

    def list_invoices(
        self,
        db: Session,
        workspace_id: int,
        account_id: Optional[int] = None,
        invoice_type: Optional[str] = None,
        payment_status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[AccountInvoice]:
        """
        List invoices with optional filters.

        Args:
            db: Database session
            workspace_id: Workspace ID
            account_id: Filter by account (optional)
            invoice_type: Filter by type (optional)
            payment_status: Filter by payment status (optional)
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of invoices
        """
        return self.account_invoice_manager.list_invoices(
            session=db,
            workspace_id=workspace_id,
            account_id=account_id,
            invoice_type=invoice_type,
            payment_status=payment_status,
            skip=skip,
            limit=limit
        )

    def update_invoice(
        self,
        db: Session,
        invoice_id: int,
        invoice_in: AccountInvoiceUpdate,
        workspace_id: int,
        user_id: int
    ) -> AccountInvoice:
        """
        Update invoice.

        Args:
            db: Database session
            invoice_id: Invoice ID
            invoice_in: Update data
            workspace_id: Workspace ID
            user_id: User updating the invoice

        Returns:
            Updated invoice

        Raises:
            HTTPException: If invoice not found or validation fails
        """
        try:
            # Update invoice using manager
            invoice = self.account_invoice_manager.update_invoice(
                session=db,
                invoice_id=invoice_id,
                invoice_data=invoice_in,
                workspace_id=workspace_id,
                user_id=user_id
            )

            # Commit transaction
            self._commit_transaction(db)
            db.refresh(invoice)

            return invoice

        except Exception as e:
            self._rollback_transaction(db)
            raise

    def delete_invoice(
        self,
        db: Session,
        invoice_id: int,
        workspace_id: int
    ) -> AccountInvoice:
        """
        Delete invoice.

        Args:
            db: Database session
            invoice_id: Invoice ID
            workspace_id: Workspace ID

        Returns:
            Deleted invoice

        Raises:
            HTTPException: If invoice not found or has payments
        """
        try:
            # Delete invoice using manager
            invoice = self.account_invoice_manager.delete_invoice(
                session=db,
                invoice_id=invoice_id,
                workspace_id=workspace_id
            )

            # Commit transaction
            self._commit_transaction(db)

            return invoice

        except Exception as e:
            self._rollback_transaction(db)
            raise


# Singleton instance
account_invoice_service = AccountInvoiceService()
