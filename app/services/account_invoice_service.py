"""Account Invoice Service for orchestrating invoice workflows"""
from decimal import Decimal
from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.services.base_service import BaseService
from app.managers.account_invoice_manager import account_invoice_manager
from app.managers.purchase_order_manager import purchase_order_manager
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
        invoice_number_search: Optional[str] = None,
        account_name_search: Optional[str] = None,
        invoice_date_from=None,
        invoice_date_to=None,
        due_date_from=None,
        due_date_to=None,
        amount_min=None,
        amount_max=None,
        skip: int = 0,
        limit: int = 100
    ) -> List[AccountInvoice]:
        """List invoices with all filters. Excludes invoices from soft-deleted accounts."""
        return self.account_invoice_manager.list_invoices(
            session=db,
            workspace_id=workspace_id,
            account_id=account_id,
            invoice_type=invoice_type,
            payment_status=payment_status,
            invoice_number_search=invoice_number_search,
            account_name_search=account_name_search,
            invoice_date_from=invoice_date_from,
            invoice_date_to=invoice_date_to,
            due_date_from=due_date_from,
            due_date_to=due_date_to,
            amount_min=amount_min,
            amount_max=amount_max,
            skip=skip,
            limit=limit,
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
        workspace_id: int,
        user_id: int
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
            po = purchase_order_manager.get_po_by_invoice_id(db, invoice_id, workspace_id)

            invoice = self.account_invoice_manager.delete_invoice(
                session=db,
                invoice_id=invoice_id,
                workspace_id=workspace_id,
                user_id=user_id
            )

            if po:
                purchase_order_manager.unlink_invoice_from_po(
                    db, po, user_id,
                    f'Draft invoice #{invoice_id} deleted',
                    event_type='invoice_draft_deleted',
                )

            self._commit_transaction(db)

            return invoice

        except Exception as e:
            self._rollback_transaction(db)
            raise


    def get_status_history(self, db: Session, invoice_id: int, workspace_id: int) -> list:
        return self.account_invoice_manager.get_status_history(
            session=db, invoice_id=invoice_id, workspace_id=workspace_id
        )

    def confirm_invoice(self, db: Session, invoice_id: int, workspace_id: int, user_id: int) -> AccountInvoice:
        try:
            po = purchase_order_manager.get_po_by_invoice_id(db, invoice_id, workspace_id)
            if po:
                approved_count, required, met = purchase_order_manager.approval_summary(db, po)
                if not met:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Requires {required} approval(s); {approved_count} so far",
                    )
                invoice_pre = self.account_invoice_manager.get_invoice(
                    db, invoice_id, workspace_id
                )
                if invoice_pre.invoice_status == 'draft':
                    invoice_pre.invoice_amount = Decimal(str(po.total_amount or 0))
                    db.flush()

            invoice = self.account_invoice_manager.confirm_invoice(
                session=db, invoice_id=invoice_id, workspace_id=workspace_id, user_id=user_id
            )

            if po:
                purchase_order_manager.apply_post_invoice_confirms(
                    db, po, workspace_id=workspace_id, user_id=user_id
                )
                purchase_order_manager.log_event(
                    db, po.id, workspace_id, 'invoice_confirmed',
                    f'Invoice #{invoice.id} confirmed — order locked',
                    user_id,
                    metadata={'invoice_id': invoice.id},
                )

            self._commit_transaction(db)
            db.refresh(invoice)
            return invoice
        except Exception:
            self._rollback_transaction(db)
            raise

    def void_invoice(self, db: Session, invoice_id: int, workspace_id: int, user_id: int, void_note: str) -> AccountInvoice:
        try:
            po = purchase_order_manager.get_po_by_invoice_id(db, invoice_id, workspace_id)

            invoice = self.account_invoice_manager.void_invoice(
                session=db, invoice_id=invoice_id, workspace_id=workspace_id,
                user_id=user_id, void_note=void_note
            )

            if po:
                purchase_order_manager.reset_approvals(db, po.id, workspace_id, user_id)
                purchase_order_manager.unlink_invoice_from_po(
                    db, po, user_id,
                    f'Invoice #{invoice_id} voided: {void_note}',
                    event_type='invoice_voided',
                )

            self._commit_transaction(db)
            db.refresh(invoice)
            return invoice
        except Exception:
            self._rollback_transaction(db)
            raise


# Singleton instance
account_invoice_service = AccountInvoiceService()
