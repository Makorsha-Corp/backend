"""Expense Order Service - transaction orchestration"""
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.services.base_service import BaseService
from app.dao.account_invoice import account_invoice_dao
from app.managers.expense_order_manager import expense_order_manager
from app.models.expense_order import ExpenseOrder
from app.models.expense_order_approver import ExpenseOrderApprover
from app.models.expense_order_event import ExpenseOrderEvent
from app.models.expense_order_item import ExpenseOrderItem
from app.models.profile import Profile
from app.schemas.expense_order import (
    ExpenseOrderCreate, ExpenseOrderUpdate, ExpenseOrderFromTemplateCreate,
    ExpenseOrderItemCreate, ExpenseOrderItemUpdate,
)
from app.schemas.account_invoice import AccountInvoiceCreate, AccountInvoiceUpdate
from app.managers.account_invoice_manager import account_invoice_manager
from app.services.approval_notification_service import (
    handle_add_approver,
    notify_invoice_action,
    notify_section_confirm_needed,
)


class ExpenseOrderService(BaseService):
    """Service for expense order workflows. Handles commit/rollback."""

    def __init__(self):
        super().__init__()
        self.manager = expense_order_manager
        self.account_invoice_manager = account_invoice_manager

    def create_expense_order(
        self, db: Session, eo_in: ExpenseOrderCreate,
        workspace_id: int, user_id: int
    ) -> ExpenseOrder:
        try:
            record = self.manager.create_expense_order(db, data=eo_in, workspace_id=workspace_id, user_id=user_id)
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    def update_expense_order(
        self, db: Session, eo_id: int, eo_in: ExpenseOrderUpdate,
        workspace_id: int, user_id: int
    ) -> ExpenseOrder:
        try:
            record = self.manager.update_expense_order(
                db, eo_id=eo_id, data=eo_in, workspace_id=workspace_id, user_id=user_id
            )
            approvals_reset = bool(getattr(record, '_approvals_reset', False))
            if approvals_reset:
                notify_section_confirm_needed(
                    db,
                    workspace_id=workspace_id,
                    entity_type='expense_order',
                    entity_id=eo_id,
                    actor_user_id=user_id,
                    order=record,
                    reason='Approvals were reset — order details changed; re-approve when ready',
                )
            self._sync_or_create_invoice(db, eo_id, workspace_id, user_id)
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    def get_expense_order(self, db: Session, eo_id: int, workspace_id: int) -> ExpenseOrder:
        return self.manager.get_expense_order(db, eo_id, workspace_id)

    def list_expense_orders(
        self, db: Session, workspace_id: int,
        expense_category: Optional[str] = None,
        account_id: Optional[int] = None,
        invoice_id: Optional[int] = None,
        skip: int = 0, limit: int = 100
    ) -> List[ExpenseOrder]:
        return self.manager.list_expense_orders(
            db, workspace_id=workspace_id,
            expense_category=expense_category, account_id=account_id, invoice_id=invoice_id,
            skip=skip, limit=limit
        )

    def delete_expense_order(self, db: Session, eo_id: int, workspace_id: int) -> None:
        try:
            self.manager.delete_expense_order(db, eo_id=eo_id, workspace_id=workspace_id)
            self._commit_transaction(db)
        except Exception:
            self._rollback_transaction(db)
            raise

    def complete_expense_order(
        self, db: Session, eo_id: int, workspace_id: int, user_id: int
    ) -> ExpenseOrder:
        try:
            eo = self.manager.get_expense_order(db, eo_id, workspace_id)
            if self.manager._is_completed(eo):
                return eo

            if not self.manager.approvals_met(db, eo):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Required approvals are not met')
            if not eo.invoice_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail='No invoice linked — set an account so a draft invoice can be created, then try again',
                )

            invoice = account_invoice_dao.get_by_id_and_workspace(db, id=eo.invoice_id, workspace_id=workspace_id)
            if not invoice:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Linked invoice not found')
            if invoice.invoice_status == 'voided':
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Linked invoice was voided — cannot complete this order')

            if invoice.invoice_status == 'draft':
                invoice = self.account_invoice_manager.confirm_invoice(
                    session=db, invoice_id=invoice.id, workspace_id=workspace_id, user_id=user_id,
                )
                notify_invoice_action(
                    db, workspace_id=workspace_id, entity_type='expense_order', entity_id=eo_id,
                    actor_user_id=user_id, invoice_id=invoice.id, action='confirmed', order=eo,
                )

            eo.completed_at = datetime.utcnow()
            eo.completed_by = user_id
            eo.updated_by = user_id
            db.flush()
            self.manager.log_event(
                db, eo_id, workspace_id, 'order_completed',
                'Invoice confirmed and expense order marked complete', user_id,
            )
            self._commit_transaction(db)
            db.refresh(eo)
            return eo
        except Exception:
            self._rollback_transaction(db)
            raise

    def void_expense_order(
        self, db: Session, eo_id: int, workspace_id: int, user_id: int, void_note: str
    ) -> ExpenseOrder:
        """Void a pre-completion expense order and delete its draft invoice, if any."""
        try:
            eo = self.manager.get_expense_order(db, eo_id, workspace_id)

            if eo.voided:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Expense order is already voided')
            if self.manager._is_completed(eo):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Cannot void a completed expense order')

            if eo.invoice_id is not None:
                invoice = account_invoice_dao.get_by_id_and_workspace(db, id=eo.invoice_id, workspace_id=workspace_id)
                if invoice and invoice.invoice_status == 'draft':
                    self.account_invoice_manager.delete_invoice(db, eo.invoice_id, workspace_id, user_id)
                self.manager.reset_approvals(
                    db, eo.id, workspace_id, user_id, reason='Cleared approvals — expense order voided',
                )
                old_invoice_id = eo.invoice_id
                eo.invoice_id = None
                db.flush()
                self.manager.log_event(
                    db, eo.id, workspace_id, 'invoice_voided',
                    f'Invoice unlinked — expense order {eo.expense_number} voided', user_id,
                    metadata={'invoice_id': old_invoice_id},
                )

            eo.voided = True
            eo.void_note = void_note
            eo.voided_at = datetime.utcnow()
            eo.voided_by = user_id
            db.flush()
            self.manager.log_event(
                db, eo.id, workspace_id, 'eo_voided',
                f'Expense order {eo.expense_number} voided. Reason: {void_note}', user_id,
                metadata={'void_note': void_note},
            )
            self._commit_transaction(db)
            db.refresh(eo)
            return eo
        except Exception:
            self._rollback_transaction(db)
            raise

    # ─── Items ─────────────────────────────────────────────────
    def add_item(
        self, db: Session, eo_id: int, item_in: ExpenseOrderItemCreate,
        workspace_id: int, user_id: int,
    ) -> ExpenseOrderItem:
        try:
            record = self.manager.add_item(
                db, eo_id=eo_id, data=item_in, workspace_id=workspace_id, user_id=user_id
            )
            eo = self.manager.get_expense_order(db, eo_id, workspace_id)
            eo.items_updated_at = datetime.utcnow()
            self._sync_or_create_invoice(db, eo_id, workspace_id, user_id)
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    def update_item(
        self, db: Session, item_id: int, item_in: ExpenseOrderItemUpdate,
        workspace_id: int, user_id: int
    ) -> ExpenseOrderItem:
        try:
            record = self.manager.update_item(
                db, item_id=item_id, data=item_in, workspace_id=workspace_id, user_id=user_id
            )
            eo = self.manager.get_expense_order(db, record.expense_order_id, workspace_id)
            eo.items_updated_at = datetime.utcnow()
            self._sync_or_create_invoice(db, record.expense_order_id, workspace_id, user_id)
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    def remove_item(
        self, db: Session, item_id: int, workspace_id: int, user_id: int
    ) -> ExpenseOrderItem:
        try:
            record = self.manager.remove_item(
                db, item_id=item_id, workspace_id=workspace_id, user_id=user_id
            )
            eo = self.manager.get_expense_order(db, record.expense_order_id, workspace_id)
            eo.items_updated_at = datetime.utcnow()
            self._sync_or_create_invoice(db, record.expense_order_id, workspace_id, user_id)
            self._commit_transaction(db)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    def get_items(self, db: Session, eo_id: int, workspace_id: int) -> List[ExpenseOrderItem]:
        return self.manager.get_items(db, eo_id, workspace_id)

    def _invoice_item_dicts(self, eo_items: List[ExpenseOrderItem]) -> list[dict]:
        return [
            {
                "line_number": i + 1,
                "description": item.description or f"Expense item {item.id}",
                "item_id": None,
                "source_order_item_id": item.id,
                "source_order_item_type": "eo_item",
                "quantity": item.quantity or Decimal("1"),
                "unit": item.unit,
                "unit_price": item.unit_price or Decimal("0"),
                "line_subtotal": item.line_subtotal or Decimal("0"),
            }
            for i, item in enumerate(eo_items)
        ]

    def _create_draft_invoice(
        self, db: Session, eo: ExpenseOrder, workspace_id: int, user_id: int
    ) -> ExpenseOrder:
        """Create + link a draft account_invoice for this order. Caller owns commit/rollback."""
        account_id = self.manager.resolve_invoice_account_id(eo)

        invoice_in = AccountInvoiceCreate(
            account_id=account_id,
            order_id=eo.id,
            order_type="expense_order",
            invoice_type="payable",
            invoice_amount=Decimal("0.00"),  # recalculated after items sync
            invoice_number=None,
            vendor_invoice_number=None,
            invoice_date=date.today(),
            due_date=eo.due_date,
            description=f"Auto-created from expense order {eo.expense_number}",
            notes=eo.description,
            allow_payments=True,
            payment_locked_reason=None,
        )

        try:
            invoice = self.account_invoice_manager.create_invoice(
                session=db,
                invoice_data=invoice_in,
                workspace_id=workspace_id,
                user_id=user_id,
            )
        except HTTPException as exc:
            if exc.status_code == status.HTTP_404_NOT_FOUND:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Cannot create invoice: selected account was not found in this workspace",
                ) from exc
            raise

        eo.invoice_id = invoice.id
        db.flush()

        eo_items = self.manager.get_items(db, eo.id, workspace_id)
        self.account_invoice_manager.sync_items_from_list(
            db, invoice, self._invoice_item_dicts(eo_items), user_id
        )

        self.manager.log_event(
            db, eo.id, workspace_id, 'invoice_created',
            f'Invoice #{invoice.id} created from expense order',
            user_id, metadata={'invoice_id': invoice.id},
        )
        return eo

    def _resync_draft_invoice(
        self, db: Session, eo: ExpenseOrder, invoice, workspace_id: int, user_id: int
    ) -> None:
        """Keep an already-linked draft invoice's items and header fields in sync with the order."""
        eo_items = self.manager.get_items(db, eo.id, workspace_id)
        self.account_invoice_manager.sync_items_from_list(
            db, invoice, self._invoice_item_dicts(eo_items), user_id
        )

        header_changes: dict = {}
        if invoice.due_date != eo.due_date:
            header_changes['due_date'] = eo.due_date
        if eo.description and invoice.notes != eo.description:
            header_changes['notes'] = eo.description
        if eo.account_id and eo.account_id != invoice.account_id:
            header_changes['account_id'] = eo.account_id
        if header_changes:
            self.account_invoice_manager.update_invoice(
                session=db, invoice_id=invoice.id,
                invoice_data=AccountInvoiceUpdate(**header_changes),
                workspace_id=workspace_id, user_id=user_id,
            )

    def _sync_or_create_invoice(
        self, db: Session, eo_id: int, workspace_id: int, user_id: int
    ) -> None:
        """Keep the linked draft invoice matching the order's current items/details, or
        auto-create one once approvals are met (if none exists yet)."""
        eo = self.manager.get_expense_order(db, eo_id, workspace_id)

        if eo.invoice_id is not None:
            invoice = account_invoice_dao.get_by_id_and_workspace(db, id=eo.invoice_id, workspace_id=workspace_id)
            if invoice and invoice.invoice_status == 'draft':
                self._resync_draft_invoice(db, eo, invoice, workspace_id, user_id)
            return

        if not self.manager.approvals_met(db, eo):
            return
        if eo.account_id is None:
            self.manager.log_event(
                db, eo_id, workspace_id, 'invoice_autocreate_skipped',
                'Approvals met but no account set — set an account to generate the invoice', user_id,
            )
            return
        items = self.manager.get_items(db, eo_id, workspace_id)
        if not items:
            return
        eo = self._create_draft_invoice(db, eo, workspace_id, user_id)
        notify_invoice_action(
            db, workspace_id=workspace_id, entity_type='expense_order', entity_id=eo_id,
            actor_user_id=user_id, invoice_id=eo.invoice_id, action='draft', order=eo,
        )

    def create_invoice_for_expense_order(
        self, db: Session, eo_id: int, workspace_id: int, user_id: int
    ) -> ExpenseOrder:
        try:
            eo = self.manager.get_expense_order(db, eo_id=eo_id, workspace_id=workspace_id)

            if eo.invoice_id is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Invoice already exists for this expense order"
                )
            if not self.manager.approvals_met(db, eo):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Required approvals are not met",
                )

            eo = self._create_draft_invoice(db, eo, workspace_id, user_id)
            notify_invoice_action(
                db,
                workspace_id=workspace_id,
                entity_type='expense_order',
                entity_id=eo_id,
                actor_user_id=user_id,
                invoice_id=eo.invoice_id,
                action='draft',
                order=eo,
            )
            self._commit_transaction(db)
            db.refresh(eo)
            return eo
        except Exception:
            self._rollback_transaction(db)
            raise

    # ─── Approvers ─────────────────────────────────────────────
    def list_approvers(
        self, db: Session, eo_id: int, workspace_id: int
    ) -> List[Tuple[ExpenseOrderApprover, Optional[Profile], Optional[str]]]:
        return self.manager.list_approvers(db, eo_id, workspace_id)

    def approval_summary_for(
        self, db: Session, eo_id: int, workspace_id: int
    ) -> Tuple[int, int, bool]:
        eo = self.manager.get_expense_order(db, eo_id, workspace_id)
        return self.manager.approval_summary(db, eo)

    def add_approver(
        self, db: Session, eo_id: int, user_id: int, workspace_id: int, assigned_by: int
    ) -> ExpenseOrderApprover:
        try:
            record = self.manager.add_approver(
                db, eo_id=eo_id, user_id=user_id, workspace_id=workspace_id, assigned_by=assigned_by
            )
            eo = self.manager.get_expense_order(db, eo_id, workspace_id)
            handle_add_approver(
                db,
                workspace_id=workspace_id,
                entity_type='expense_order',
                entity_id=eo_id,
                actor_user_id=assigned_by,
                approver_user_id=user_id,
                approver_record_id=record.id,
                order=eo,
            )
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    def remove_approver(
        self, db: Session, eo_id: int, user_id: int, workspace_id: int, performed_by: int
    ) -> None:
        try:
            self.manager.remove_approver(
                db, eo_id=eo_id, user_id=user_id, workspace_id=workspace_id, performed_by=performed_by
            )
            self._commit_transaction(db)
        except Exception:
            self._rollback_transaction(db)
            raise

    def approve_as_me(
        self, db: Session, eo_id: int, user_id: int, workspace_id: int
    ) -> ExpenseOrderApprover:
        try:
            record = self.manager.set_approval(
                db, eo_id=eo_id, user_id=user_id, workspace_id=workspace_id, approved=True
            )
            self._sync_or_create_invoice(db, eo_id, workspace_id, user_id)
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    def unapprove_as_me(
        self, db: Session, eo_id: int, user_id: int, workspace_id: int
    ) -> ExpenseOrderApprover:
        try:
            record = self.manager.set_approval(
                db, eo_id=eo_id, user_id=user_id, workspace_id=workspace_id, approved=False
            )
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    # ─── Events ────────────────────────────────────────────────
    def list_events(
        self, db: Session, eo_id: int, workspace_id: int
    ) -> List[Tuple[ExpenseOrderEvent, Optional[Profile]]]:
        return self.manager.list_events(db, eo_id, workspace_id)

    # ─── Templates ─────────────────────────────────────────────
    def create_expense_order_from_template(
        self, db: Session, template_id: int, overrides: ExpenseOrderFromTemplateCreate,
        workspace_id: int, user_id: int
    ) -> ExpenseOrder:
        try:
            record = self.manager.create_expense_order_from_template(
                db, template_id=template_id, workspace_id=workspace_id, user_id=user_id, overrides=overrides,
            )
            self._sync_or_create_invoice(db, record.id, workspace_id, user_id)
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise


expense_order_service = ExpenseOrderService()
