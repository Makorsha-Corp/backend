"""
Account Invoice Manager

Business logic for account invoice operations.
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from decimal import Decimal

from app.managers.base_manager import BaseManager
from app.models.account_invoice import AccountInvoice
from app.schemas.account_invoice import AccountInvoiceCreate, AccountInvoiceUpdate
from app.dao.account_invoice import account_invoice_dao
from app.dao.account import account_dao
from app.utils.audit_logger import log_financial_audit, create_change_dict, extract_relevant_fields


class AccountInvoiceManager(BaseManager[AccountInvoice]):
    """
    Manager for account invoice business logic.

    Handles CRUD operations for invoices with workspace isolation.
    """

    def __init__(self):
        super().__init__(AccountInvoice)
        self.account_invoice_dao = account_invoice_dao
        self.account_dao = account_dao

    def create_invoice(
        self,
        session: Session,
        invoice_data: AccountInvoiceCreate,
        workspace_id: int,
        user_id: int
    ) -> AccountInvoice:
        """
        Create new invoice.

        Args:
            session: Database session
            invoice_data: Invoice creation data
            workspace_id: Workspace ID
            user_id: User creating the invoice

        Returns:
            Created invoice

        Raises:
            HTTPException: If account not found or validation fails
        """
        # Validate account exists in workspace
        account = self.account_dao.get_by_id_and_workspace(
            session, id=invoice_data.account_id, workspace_id=workspace_id
        )
        if not account:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Account with ID {invoice_data.account_id} not found"
            )

        # Check if account is deleted
        if account.is_deleted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot create invoice for deleted account"
            )

        # Create invoice with audit fields
        invoice_dict = invoice_data.model_dump()
        invoice_dict['workspace_id'] = workspace_id
        invoice_dict['created_by'] = user_id
        invoice_dict['paid_amount'] = Decimal('0.00')
        invoice_dict['payment_status'] = 'unpaid'

        invoice = self.account_invoice_dao.create(session, obj_in=invoice_dict)

        # Audit log
        log_financial_audit(
            session=session,
            workspace_id=workspace_id,
            entity_type='invoice',
            entity_id=invoice.id,
            action_type='created',
            performed_by=user_id,
            related_entity_type='account',
            related_entity_id=invoice.account_id,
            changes=create_change_dict(after=extract_relevant_fields(
                invoice, ['invoice_type', 'invoice_amount', 'invoice_number', 'invoice_date', 'due_date']
            )),
            description=f"{invoice.invoice_type.capitalize()} invoice created for account ID {invoice.account_id}"
        )

        return invoice

    def update_invoice(
        self,
        session: Session,
        invoice_id: int,
        invoice_data: AccountInvoiceUpdate,
        workspace_id: int,
        user_id: int
    ) -> AccountInvoice:
        """
        Update invoice.

        Args:
            session: Database session
            invoice_id: Invoice ID
            invoice_data: Update data
            workspace_id: Workspace ID
            user_id: User updating the invoice

        Returns:
            Updated invoice

        Raises:
            HTTPException: If invoice not found or validation fails
        """
        # Get invoice
        invoice = self.account_invoice_dao.get_by_id_and_workspace(
            session, id=invoice_id, workspace_id=workspace_id
        )
        if not invoice:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Invoice with ID {invoice_id} not found"
            )

        # If changing account, validate new account exists
        if invoice_data.account_id and invoice_data.account_id != invoice.account_id:
            account = self.account_dao.get_by_id_and_workspace(
                session, id=invoice_data.account_id, workspace_id=workspace_id
            )
            if not account:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Account with ID {invoice_data.account_id} not found"
                )
            if account.is_deleted:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot assign invoice to deleted account"
                )

        # Capture before state for audit
        before_state = extract_relevant_fields(
            invoice, ['invoice_type', 'invoice_amount', 'invoice_number', 'invoice_date', 'due_date', 'payment_status']
        )

        # Update invoice with audit fields
        update_dict = invoice_data.model_dump(exclude_unset=True)
        update_dict['updated_by'] = user_id

        updated_invoice = self.account_invoice_dao.update(session, db_obj=invoice, obj_in=update_dict)

        # Capture after state for audit
        after_state = extract_relevant_fields(
            updated_invoice, ['invoice_type', 'invoice_amount', 'invoice_number', 'invoice_date', 'due_date', 'payment_status']
        )

        # Audit log
        log_financial_audit(
            session=session,
            workspace_id=workspace_id,
            entity_type='invoice',
            entity_id=invoice.id,
            action_type='updated',
            performed_by=user_id,
            related_entity_type='account',
            related_entity_id=invoice.account_id,
            changes=create_change_dict(before=before_state, after=after_state),
            description=f"Invoice {invoice.invoice_number or invoice.id} updated"
        )

        return updated_invoice

    def get_invoice(
        self,
        session: Session,
        invoice_id: int,
        workspace_id: int
    ) -> AccountInvoice:
        """
        Get invoice by ID.

        Args:
            session: Database session
            invoice_id: Invoice ID
            workspace_id: Workspace ID

        Returns:
            Invoice

        Raises:
            HTTPException: If invoice not found
        """
        invoice = self.account_invoice_dao.get_by_id_and_workspace(
            session, id=invoice_id, workspace_id=workspace_id
        )

        if not invoice:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Invoice with ID {invoice_id} not found"
            )

        return invoice

    def list_invoices(
        self,
        session: Session,
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
            session: Database session
            workspace_id: Workspace ID
            account_id: Filter by account (optional)
            invoice_type: Filter by type ('payable' or 'receivable') (optional)
            payment_status: Filter by payment status (optional)
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of invoices
        """
        # Apply filters based on parameters
        if account_id:
            return self.account_invoice_dao.get_by_account(
                session, account_id=account_id, workspace_id=workspace_id, skip=skip, limit=limit
            )
        elif invoice_type:
            return self.account_invoice_dao.get_by_type(
                session, invoice_type=invoice_type, workspace_id=workspace_id, skip=skip, limit=limit
            )
        elif payment_status:
            return self.account_invoice_dao.get_by_status(
                session, payment_status=payment_status, workspace_id=workspace_id, skip=skip, limit=limit
            )
        else:
            return self.account_invoice_dao.get_by_workspace(
                session, workspace_id=workspace_id, skip=skip, limit=limit
            )

    def delete_invoice(
        self,
        session: Session,
        invoice_id: int,
        workspace_id: int
    ) -> AccountInvoice:
        """
        Delete invoice (only if no payments exist).

        Args:
            session: Database session
            invoice_id: Invoice ID
            workspace_id: Workspace ID

        Returns:
            Deleted invoice

        Raises:
            HTTPException: If invoice not found or has payments
        """
        invoice = self.account_invoice_dao.get_by_id_and_workspace(
            session, id=invoice_id, workspace_id=workspace_id
        )

        if not invoice:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Invoice with ID {invoice_id} not found"
            )

        # Check if invoice has payments
        if invoice.paid_amount > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot delete invoice with existing payments"
            )

        # Audit log before deletion
        log_financial_audit(
            session=session,
            workspace_id=workspace_id,
            entity_type='invoice',
            entity_id=invoice.id,
            action_type='deleted',
            performed_by=0,  # No user_id passed to delete method currently
            related_entity_type='account',
            related_entity_id=invoice.account_id,
            changes=create_change_dict(before=extract_relevant_fields(
                invoice, ['invoice_type', 'invoice_amount', 'invoice_number', 'invoice_date']
            )),
            description=f"Invoice {invoice.invoice_number or invoice.id} deleted"
        )

        # Delete invoice
        self.account_invoice_dao.remove(session, id=invoice_id)
        return invoice


# Singleton instance
account_invoice_manager = AccountInvoiceManager()
