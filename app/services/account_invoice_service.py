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
from app.schemas.invoice_item import InvoiceItemResponse


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
        invoice_status: Optional[str] = None,
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
            invoice_status=invoice_status,
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


    def get_events(self, db: Session, invoice_id: int, workspace_id: int) -> list:
        return self.account_invoice_manager.get_events(
            session=db, invoice_id=invoice_id, workspace_id=workspace_id
        )

    def get_items(self, db: Session, invoice_id: int, workspace_id: int) -> list:
        return self.account_invoice_manager.get_items(
            session=db, invoice_id=invoice_id, workspace_id=workspace_id
        )

    def revert_to_draft(self, db: Session, invoice_id: int, workspace_id: int, user_id: int):
        try:
            invoice = self.account_invoice_manager.revert_to_draft(
                session=db, invoice_id=invoice_id, workspace_id=workspace_id, user_id=user_id
            )
            self._commit_transaction(db)
            db.refresh(invoice)
            return invoice
        except Exception:
            self._rollback_transaction(db)
            raise

    def resync_items(self, db: Session, invoice_id: int, workspace_id: int, user_id: int):
        """Re-pull items from the linked order into the draft invoice."""
        try:
            invoice = self.account_invoice_manager.get_invoice(db, invoice_id, workspace_id)
            if invoice.invoice_status != 'draft':
                from fastapi import HTTPException, status as http_status
                raise HTTPException(
                    status_code=http_status.HTTP_400_BAD_REQUEST,
                    detail="Can only resync items on draft invoices.",
                )
            if not invoice.order_id or not invoice.order_type:
                from fastapi import HTTPException, status as http_status
                raise HTTPException(
                    status_code=http_status.HTTP_400_BAD_REQUEST,
                    detail="This invoice is not linked to an order — resync is not applicable.",
                )

            if invoice.order_type == 'purchase_order':
                from app.services.purchase_order_service import purchase_order_service
                po = purchase_order_manager.get_purchase_order(db, invoice.order_id, workspace_id)
                items = purchase_order_service._build_invoice_items_from_po(po)
            elif invoice.order_type == 'expense_order':
                from app.managers.expense_order_manager import expense_order_manager
                eo_items = expense_order_manager.get_items(db, invoice.order_id, workspace_id)
                from decimal import Decimal as D
                items = [
                    {
                        "line_number": i + 1,
                        "description": item.description or f"Expense item {item.id}",
                        "item_id": None,
                        "source_order_item_id": item.id,
                        "source_order_item_type": "eo_item",
                        "quantity": item.quantity or D("1"),
                        "unit": item.unit,
                        "unit_price": item.unit_price or D("0"),
                        "line_subtotal": item.line_subtotal or D("0"),
                    }
                    for i, item in enumerate(eo_items)
                ]
            elif invoice.order_type == 'sales_order':
                from app.managers.sales_manager import sales_manager
                order = sales_manager.get_sales_order(db, invoice.order_id, workspace_id)
                so_items = getattr(order, 'items', []) or []
                items = [
                    {
                        "line_number": i + 1,
                        "description": item.item_name or f"Item {item.item_id}",
                        "item_id": item.item_id,
                        "source_order_item_id": item.id,
                        "source_order_item_type": "so_item",
                        "quantity": item.quantity_ordered,
                        "unit": item.item_unit,
                        "unit_price": item.unit_price,
                        "line_subtotal": item.line_total,
                    }
                    for i, item in enumerate(so_items)
                ]
            else:
                items = []

            self.account_invoice_manager.sync_items_from_list(db, invoice, items, user_id)
            self._commit_transaction(db)
            db.refresh(invoice)
            return invoice
        except Exception:
            self._rollback_transaction(db)
            raise

    def confirm_invoice(self, db: Session, invoice_id: int, workspace_id: int, user_id: int) -> AccountInvoice:
        try:
            po = purchase_order_manager.get_po_by_invoice_id(db, invoice_id, workspace_id)
            if po:
                if not purchase_order_manager._base_sections_confirmed(po):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail='Confirm supplier, order details, and items before finalizing',
                    )
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

            if po:
                po_items = purchase_order_manager.item_dao.get_by_order(
                    db, purchase_order_id=po.id, workspace_id=workspace_id
                )
                if any(
                    Decimal(str(i.quantity_received or 0)) > 0 for i in po_items
                ):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail='Cannot void invoice after receiving has been recorded on the linked order',
                    )

            invoice = self.account_invoice_manager.void_invoice(
                session=db, invoice_id=invoice_id, workspace_id=workspace_id,
                user_id=user_id, void_note=void_note
            )

            if po:
                purchase_order_manager.reset_approvals(db, po.id, workspace_id, user_id)
                purchase_order_manager.unlink_invoice_from_po(
                    db, po, user_id,
                    f'Invoice #{invoice_id} voided',
                    event_type='invoice_voided',
                    extra_metadata={
                        'changes': [{
                            'field': 'void_note',
                            'label': 'Void reason',
                            'from_value': None,
                            'to_value': void_note,
                        }],
                    },
                )

            self._commit_transaction(db)
            db.refresh(invoice)
            return invoice
        except Exception:
            self._rollback_transaction(db)
            raise


# Singleton instance
account_invoice_service = AccountInvoiceService()
