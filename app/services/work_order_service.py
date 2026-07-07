"""Work Order Service - transaction orchestration"""
from datetime import date
from decimal import Decimal
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.services.base_service import BaseService
from app.dao.account_invoice import account_invoice_dao
from app.managers.work_order_manager import work_order_manager
from app.managers.account_invoice_manager import account_invoice_manager
from app.models.work_order import WorkOrder
from app.models.work_order_approver import WorkOrderApprover
from app.models.work_order_event import WorkOrderEvent
from app.models.work_order_item import WorkOrderItem
from app.models.profile import Profile
from app.models.enums import WorkOrderPriorityEnum, WorkOrderStatusEnum, MachineEventTypeEnum
from app.schemas.work_order import WorkOrderCreate, WorkOrderUpdate
from app.schemas.work_order_item import WorkOrderItemCreate, WorkOrderItemUpdate
from app.schemas.work_order_template import WorkOrderFromTemplateCreate
from app.schemas.account_invoice import AccountInvoiceCreate
from app.services.approval_notification_service import (
    handle_add_approver,
    notify_invoice_action,
    notify_section_confirm_needed,
)


class WorkOrderService(BaseService):
    """Service for work order workflows. Handles commit/rollback."""

    def __init__(self):
        super().__init__()
        self.manager = work_order_manager
        self.account_invoice_manager = account_invoice_manager

    def create_work_order(
        self, db: Session, wo_in: WorkOrderCreate,
        workspace_id: int, user_id: int
    ) -> WorkOrder:
        try:
            record = self.manager.create_work_order(db, data=wo_in, workspace_id=workspace_id, user_id=user_id)
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    def create_work_order_from_template(
        self, db: Session, template_id: int, overrides: WorkOrderFromTemplateCreate,
        workspace_id: int, user_id: int
    ) -> WorkOrder:
        try:
            record = self.manager.create_work_order_from_template(
                db, template_id=template_id, workspace_id=workspace_id, user_id=user_id, overrides=overrides,
            )
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    def update_work_order(
        self, db: Session, wo_id: int, wo_in: WorkOrderUpdate,
        workspace_id: int, user_id: int
    ) -> WorkOrder:
        try:
            record = self.manager.update_work_order(db, wo_id=wo_id, data=wo_in, workspace_id=workspace_id, user_id=user_id)
            if bool(getattr(record, '_approvals_reset', False)):
                notify_section_confirm_needed(
                    db, workspace_id=workspace_id, entity_type='work_order', entity_id=wo_id,
                    actor_user_id=user_id, order=record,
                    reason='Approvals were reset — order details changed; re-approve when ready',
                )
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    def get_work_order(self, db: Session, wo_id: int, workspace_id: int) -> WorkOrder:
        return self.manager.get_work_order(db, wo_id, workspace_id)

    def list_work_orders(
        self, db: Session, workspace_id: int,
        work_order_type_id: Optional[int] = None,
        wo_status: Optional[WorkOrderStatusEnum] = None,
        priority: Optional[WorkOrderPriorityEnum] = None,
        factory_id: Optional[int] = None,
        machine_id: Optional[int] = None,
        skip: int = 0, limit: int = 100
    ) -> List[WorkOrder]:
        return self.manager.list_work_orders(
            db, workspace_id=workspace_id,
            work_order_type_id=work_order_type_id, wo_status=wo_status, priority=priority,
            factory_id=factory_id, machine_id=machine_id,
            skip=skip, limit=limit
        )

    def delete_work_order(self, db: Session, wo_id: int, workspace_id: int, user_id: int) -> WorkOrder:
        try:
            record = self.manager.delete_work_order(db, wo_id=wo_id, workspace_id=workspace_id, user_id=user_id)
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    # ─── Lifecycle ───────────────────────────────────────────────
    def start_work_order(self, db: Session, wo_id: int, workspace_id: int, user_id: int) -> WorkOrder:
        try:
            record = self.manager.start_work_order(db, wo_id=wo_id, workspace_id=workspace_id, user_id=user_id)
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    def complete_work_order(
        self, db: Session, wo_id: int, workspace_id: int, user_id: int,
        completion_notes: Optional[str] = None,
        machine_status: Optional[str] = None,
    ) -> WorkOrder:
        try:
            wo = self.manager.get_work_order(db, wo_id, workspace_id)
            if wo.status == WorkOrderStatusEnum.COMPLETED.value:
                return wo
            if wo.status != WorkOrderStatusEnum.IN_PROGRESS.value:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Work order must be in progress before it can be completed')

            if wo.account_id is not None:
                if not wo.invoice_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail='No invoice linked — create an invoice for this external work before completing',
                    )
                invoice = account_invoice_dao.get_by_id_and_workspace(db, id=wo.invoice_id, workspace_id=workspace_id)
                if not invoice:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Linked invoice not found')
                if invoice.invoice_status == 'voided':
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Linked invoice was voided — cannot complete this order')
                if invoice.invoice_status == 'draft':
                    invoice = self.account_invoice_manager.confirm_invoice(
                        session=db, invoice_id=invoice.id, workspace_id=workspace_id, user_id=user_id,
                    )
                    notify_invoice_action(
                        db, workspace_id=workspace_id, entity_type='work_order', entity_id=wo_id,
                        actor_user_id=user_id, invoice_id=invoice.id, action='confirmed', order=wo,
                    )

            record = self.manager.finalize_completion(
                db, wo, user_id,
                completion_notes=completion_notes,
                machine_status=MachineEventTypeEnum(machine_status) if machine_status else None,
            )
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    def void_work_order(self, db: Session, wo_id: int, workspace_id: int, user_id: int, void_note: str) -> WorkOrder:
        try:
            wo = self.manager.get_work_order(db, wo_id, workspace_id)
            if wo.invoice_id is not None:
                invoice = account_invoice_dao.get_by_id_and_workspace(db, id=wo.invoice_id, workspace_id=workspace_id)
                if invoice and invoice.invoice_status == 'draft':
                    self.account_invoice_manager.delete_invoice(db, wo.invoice_id, workspace_id, user_id)
                    old_invoice_id = wo.invoice_id
                    wo.invoice_id = None
                    db.flush()
                    self.manager.log_event(
                        db, wo.id, workspace_id, 'invoice_voided',
                        f'Invoice unlinked — work order {wo.work_order_number} voided', user_id,
                        metadata={'invoice_id': old_invoice_id},
                    )

            record = self.manager.void_work_order(db, wo_id=wo_id, workspace_id=workspace_id, user_id=user_id, void_note=void_note)
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    # ─── Invoice ─────────────────────────────────────────────────
    def create_invoice_for_work_order(self, db: Session, wo_id: int, workspace_id: int, user_id: int) -> WorkOrder:
        try:
            wo = self.manager.get_work_order(db, wo_id, workspace_id)
            if wo.invoice_id is not None:
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Invoice already exists for this work order")
            account_id = self.manager.resolve_invoice_account_id(wo)

            invoice_in = AccountInvoiceCreate(
                account_id=account_id,
                order_id=wo.id,
                order_type="work_order",
                invoice_type="payable",
                invoice_amount=Decimal("0.00"),
                invoice_number=None,
                vendor_invoice_number=None,
                invoice_date=date.today(),
                due_date=wo.end_date,
                description=f"Auto-created from work order {wo.work_order_number}",
                notes=wo.description,
                allow_payments=True,
                payment_locked_reason=None,
            )
            try:
                invoice = self.account_invoice_manager.create_invoice(
                    session=db, invoice_data=invoice_in, workspace_id=workspace_id, user_id=user_id,
                )
            except HTTPException as exc:
                if exc.status_code == status.HTTP_404_NOT_FOUND:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="Cannot create invoice: selected account was not found in this workspace",
                    ) from exc
                raise

            wo.invoice_id = invoice.id
            db.flush()

            self.account_invoice_manager.sync_items_from_list(
                db, invoice,
                [{
                    "line_number": 1,
                    "description": wo.title,
                    "item_id": None,
                    "source_order_item_id": None,
                    "source_order_item_type": "wo_labor",
                    "quantity": Decimal("1"),
                    "unit": None,
                    "unit_price": wo.cost or Decimal("0"),
                    "line_subtotal": wo.cost or Decimal("0"),
                }],
                user_id,
            )

            self.manager.log_event(
                db, wo.id, workspace_id, 'invoice_created',
                f'Invoice #{invoice.id} created from work order', user_id,
                metadata={'invoice_id': invoice.id},
            )
            notify_invoice_action(
                db, workspace_id=workspace_id, entity_type='work_order', entity_id=wo_id,
                actor_user_id=user_id, invoice_id=invoice.id, action='draft', order=wo,
            )
            self._commit_transaction(db)
            db.refresh(wo)
            return wo
        except Exception:
            self._rollback_transaction(db)
            raise

    # ─── Approvers ───────────────────────────────────────────────
    def list_approvers(
        self, db: Session, wo_id: int, workspace_id: int
    ) -> List[Tuple[WorkOrderApprover, Optional[Profile], Optional[str]]]:
        return self.manager.list_approvers(db, wo_id, workspace_id)

    def approval_summary_for(self, db: Session, wo_id: int, workspace_id: int) -> Tuple[int, int, bool]:
        wo = self.manager.get_work_order(db, wo_id, workspace_id)
        return self.manager.approval_summary(db, wo)

    def add_approver(
        self, db: Session, wo_id: int, user_id: int, workspace_id: int, assigned_by: int
    ) -> WorkOrderApprover:
        try:
            record = self.manager.add_approver(db, wo_id=wo_id, user_id=user_id, workspace_id=workspace_id, assigned_by=assigned_by)
            wo = self.manager.get_work_order(db, wo_id, workspace_id)
            handle_add_approver(
                db, workspace_id=workspace_id, entity_type='work_order', entity_id=wo_id,
                actor_user_id=assigned_by, approver_user_id=user_id, approver_record_id=record.id, order=wo,
            )
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    def remove_approver(self, db: Session, wo_id: int, user_id: int, workspace_id: int, performed_by: int) -> None:
        try:
            self.manager.remove_approver(db, wo_id=wo_id, user_id=user_id, workspace_id=workspace_id, performed_by=performed_by)
            self._commit_transaction(db)
        except Exception:
            self._rollback_transaction(db)
            raise

    def approve_as_me(self, db: Session, wo_id: int, user_id: int, workspace_id: int) -> WorkOrderApprover:
        try:
            record = self.manager.set_approval(db, wo_id=wo_id, user_id=user_id, workspace_id=workspace_id, approved=True)
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    def unapprove_as_me(self, db: Session, wo_id: int, user_id: int, workspace_id: int) -> WorkOrderApprover:
        try:
            record = self.manager.set_approval(db, wo_id=wo_id, user_id=user_id, workspace_id=workspace_id, approved=False)
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    # ─── Events ──────────────────────────────────────────────────
    def list_events(self, db: Session, wo_id: int, workspace_id: int) -> List[Tuple[WorkOrderEvent, Optional[Profile]]]:
        return self.manager.list_events(db, wo_id, workspace_id)

    # ─── Work Order Items ───────────────────────────────────────
    def add_item(self, db: Session, item_in: WorkOrderItemCreate, workspace_id: int, user_id: int) -> WorkOrderItem:
        try:
            record = self.manager.add_item(db, data=item_in, workspace_id=workspace_id, user_id=user_id)
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    def update_item(self, db: Session, item_id: int, item_in: WorkOrderItemUpdate, workspace_id: int, user_id: int) -> WorkOrderItem:
        try:
            record = self.manager.update_item(db, item_id=item_id, data=item_in, workspace_id=workspace_id, user_id=user_id)
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    def remove_item(self, db: Session, item_id: int, workspace_id: int, user_id: int) -> WorkOrderItem:
        try:
            record = self.manager.remove_item(db, item_id=item_id, workspace_id=workspace_id, user_id=user_id)
            self._commit_transaction(db)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    def get_items(self, db: Session, wo_id: int, workspace_id: int) -> List[WorkOrderItem]:
        return self.manager.get_items(db, wo_id, workspace_id)


work_order_service = WorkOrderService()
