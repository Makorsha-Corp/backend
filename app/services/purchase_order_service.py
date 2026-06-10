"""Purchase Order Service - transaction orchestration"""
import logging
from datetime import date
from decimal import Decimal
from typing import List, Optional
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status

from app.services.base_service import BaseService
from app.managers.purchase_order_manager import purchase_order_manager
from app.managers.account_invoice_manager import account_invoice_manager
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem
from app.models.order_workflow import OrderWorkflow
from app.dao.purchase_order import purchase_order_dao
from app.dao.transfer_order import transfer_order_dao
from app.dao.machine import machine_dao
from app.dao.factory import factory_dao
from app.dao.project_component import project_component_dao
from app.schemas.purchase_order import (
    PurchaseOrderCreate, PurchaseOrderUpdate,
    PurchaseOrderItemCreate, PurchaseOrderItemUpdate,
    PurchaseOrderItemSyncRequest,
    ActiveOrderRow,
)
from app.dao.account_invoice import account_invoice_dao
from app.schemas.account_invoice import AccountInvoiceCreate, AccountInvoiceUpdate

logger = logging.getLogger(__name__)


class PurchaseOrderService(BaseService):
    """Service for purchase order workflows. Handles commit/rollback."""

    def __init__(self):
        super().__init__()
        self.manager = purchase_order_manager
        self.account_invoice_manager = account_invoice_manager

    def _integrity_context(self, exc: IntegrityError) -> tuple[str | None, str | None]:
        orig = getattr(exc, 'orig', None)
        diag = getattr(orig, 'diag', None) if orig else None
        table = getattr(diag, 'table_name', None) if diag else None
        column = getattr(diag, 'column_name', None) if diag else None
        return table, column

    def _handle_item_integrity_error(
        self, exc: IntegrityError, *, phase: str = 'items'
    ) -> None:
        orig = getattr(exc, 'orig', None)
        pgcode = getattr(orig, 'pgcode', None) if orig else None
        err = str(exc).lower()
        orig_err = str(orig).lower() if orig else ''
        combined = f'{err} {orig_err}'
        table, column = self._integrity_context(exc)

        if pgcode == '23514' or 'check constraint' in combined or '23514' in combined:
            if (
                'quantity_ordered' in combined
                or 'quantity_received' in combined
                or ('ordered' in combined and 'received' in combined)
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail='Ordered quantity cannot be less than received quantity',
                ) from exc
            if 'invoice_amount' in combined or 'paid_amount' in combined:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail='Order total cannot be less than amount already paid on the linked invoice',
                ) from exc
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Update violates a business rule. Check amounts and quantities.',
            ) from exc

        if pgcode == '23505' or 'unique constraint' in combined or 'duplicate' in combined:
            if table == 'account_invoices' or phase == 'invoice':
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail='A draft invoice for this order already exists',
                ) from exc
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail='That catalog item is already on this purchase order',
            ) from exc

        if pgcode == '23502' or 'not-null constraint' in combined or 'null value' in combined:
            if table in ('account_invoices', 'financial_audit_logs', 'invoice_status_tracker') or phase == 'invoice':
                loc = f' ({table}.{column})' if table and column else ''
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f'Could not sync the draft invoice for this order{loc}. '
                        'Save the supplier section again, then retry editing items.'
                    ),
                ) from exc
            loc = f' ({table}.{column})' if table and column else ''
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f'Order line data is incomplete{loc}. Refresh the page and try again.'
                ),
            ) from exc

        if pgcode == '23503' or 'foreign key constraint' in combined:
            if table in ('account_invoices', 'financial_audit_logs') or phase == 'invoice':
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail='The selected supplier or linked invoice is invalid. Refresh and try again.',
                ) from exc
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='A linked catalog item or order reference is missing. Refresh the page and try again.',
            ) from exc

        logger.exception('IntegrityError during PO %s operation (table=%s column=%s)', phase, table, column)
        if phase == 'invoice':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Could not sync the draft invoice after saving items. Refresh and try again.',
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Could not save order items. Refresh the page and try again.',
        ) from exc

    def _sync_draft_invoice_for_po(
        self,
        db: Session,
        po: PurchaseOrder,
        workspace_id: int,
        user_id: int,
    ) -> None:
        """Ensure a draft payable invoice exists and mirrors PO supplier + totals."""
        if self.manager.is_po_financially_locked(db, po):
            return
        if po.account_id is None:
            return

        total = Decimal(str(po.total_amount or 0))
        description = f"Purchase order {po.po_number}"
        notes = po.order_note or po.description

        if po.invoice_id is None:
            invoice_in = AccountInvoiceCreate(
                account_id=po.account_id,
                order_id=None,
                invoice_type="payable",
                invoice_amount=total,
                invoice_number=None,
                vendor_invoice_number=None,
                invoice_date=date.today(),
                due_date=None,
                description=description,
                notes=notes,
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
                    return
                raise
            po.invoice_id = invoice.id
            self.manager.log_event(
                db,
                po.id,
                workspace_id,
                'invoice_draft_created',
                f'Draft invoice #{invoice.id} linked to {po.po_number}',
                user_id,
                metadata={'invoice_id': invoice.id},
            )
            db.flush()
            return

        invoice = account_invoice_dao.get_by_id_and_workspace(
            db, id=po.invoice_id, workspace_id=workspace_id
        )
        if not invoice or invoice.invoice_status != 'draft':
            return

        paid = Decimal(str(invoice.paid_amount or 0))
        if total < paid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f'Order total ({total}) cannot be less than amount already paid '
                    f'on the linked invoice ({paid})'
                ),
            )

        new_account_id = po.account_id
        amount_changed = Decimal(str(invoice.invoice_amount)) != total
        account_changed = invoice.account_id != new_account_id
        notes_changed = (invoice.notes or None) != (notes or None)
        desc_changed = (invoice.description or None) != description

        if (amount_changed or account_changed) and po.invoice_confirmed:
            po.invoice_confirmed = False
            self.manager.reset_approvals(
                db,
                po.id,
                workspace_id,
                user_id,
                reason='Draft invoice changed after order update',
            )
            self.manager.log_event(
                db,
                po.id,
                workspace_id,
                'invoice_unconfirmed',
                'Draft invoice unconfirmed after order sync',
                user_id,
            )

        invoice_updates: dict = {}
        if account_changed:
            invoice_updates['account_id'] = new_account_id
        if amount_changed:
            invoice_updates['invoice_amount'] = total
        if desc_changed:
            invoice_updates['description'] = description
        if notes_changed:
            invoice_updates['notes'] = notes
        if invoice_updates:
            self.account_invoice_manager.update_invoice(
                db,
                po.invoice_id,
                AccountInvoiceUpdate(**invoice_updates),
                workspace_id,
                user_id,
            )
            db.flush()

    def create_purchase_order(
        self, db: Session, po_in: PurchaseOrderCreate,
        workspace_id: int, user_id: int
    ) -> PurchaseOrder:
        last_integrity: IntegrityError | None = None
        try:
            for _ in range(5):
                try:
                    record = self.manager.create_purchase_order(
                        db, data=po_in, workspace_id=workspace_id, user_id=user_id
                    )
                    self._sync_draft_invoice_for_po(db, record, workspace_id, user_id)
                    self._commit_transaction(db)
                    db.refresh(record)
                    return record
                except IntegrityError as exc:
                    last_integrity = exc
                    self._rollback_transaction(db)
                    err = str(exc).lower()
                    if 'po_number' not in err and 'uq_po_workspace_number' not in err:
                        raise
            if last_integrity:
                err = str(last_integrity).lower()
                if 'po_number' in err or 'uq_po_workspace_number' in err:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Could not assign a unique PO number. Please try again.",
                    ) from last_integrity
                raise last_integrity
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create purchase order",
            )
        except HTTPException:
            raise
        except Exception:
            self._rollback_transaction(db)
            raise

    def update_purchase_order(
        self, db: Session, po_id: int, po_in: PurchaseOrderUpdate,
        workspace_id: int, user_id: int
    ) -> PurchaseOrder:
        try:
            record = self.manager.update_purchase_order(
                db, po_id=po_id, data=po_in, workspace_id=workspace_id, user_id=user_id
            )
            self._sync_draft_invoice_for_po(db, record, workspace_id, user_id)
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except IntegrityError as exc:
            self._rollback_transaction(db)
            self._handle_item_integrity_error(exc, phase='invoice')
        except HTTPException:
            self._rollback_transaction(db)
            raise
        except Exception:
            self._rollback_transaction(db)
            raise

    def get_purchase_order(self, db: Session, po_id: int, workspace_id: int) -> PurchaseOrder:
        return self.manager.get_purchase_order(db, po_id, workspace_id)

    def list_purchase_orders(
        self, db: Session, workspace_id: int,
        account_id: Optional[int] = None,
        invoice_id: Optional[int] = None,
        skip: int = 0, limit: int = 100
    ) -> List[PurchaseOrder]:
        return self.manager.list_purchase_orders(
            db, workspace_id=workspace_id,
            account_id=account_id,
            invoice_id=invoice_id,
            skip=skip, limit=limit
        )

    def list_active_orders_for_context(
        self,
        db: Session,
        *,
        workspace_id: int,
        machine_id: Optional[int] = None,
        factory_id: Optional[int] = None,
        project_component_id: Optional[int] = None,
    ) -> List[ActiveOrderRow]:
        """
        Active (non-terminal) purchase orders for a destination plus incomplete transfer orders
        touching the same logical location. Exactly one scope id must be provided.
        """
        scopes = sum(1 for x in (machine_id, factory_id, project_component_id) if x is not None)
        if scopes != 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Provide exactly one of machine_id, factory_id, project_component_id",
            )

        if machine_id is not None:
            if machine_dao.get_by_id_and_workspace(db, id=machine_id, workspace_id=workspace_id) is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Machine not found")
            dest_type, dest_id, loc_type, loc_id = "machine", machine_id, "machine", machine_id
        elif factory_id is not None:
            if factory_dao.get_by_id_and_workspace(db, id=factory_id, workspace_id=workspace_id) is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Factory not found")
            dest_type, dest_id, loc_type, loc_id = "storage", factory_id, "storage", factory_id
        else:
            assert project_component_id is not None
            if project_component_dao.get_by_id_and_workspace(
                db, id=project_component_id, workspace_id=workspace_id
            ) is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project component not found")
            dest_type, dest_id, loc_type, loc_id = "project", project_component_id, "project", project_component_id

        pos = purchase_order_dao.list_for_destination(
            db,
            workspace_id=workspace_id,
            destination_type=dest_type,
            destination_id=dest_id,
        )
        tos = transfer_order_dao.list_touching_location_incomplete(
            db,
            workspace_id=workspace_id,
            location_type=loc_type,
            location_id=loc_id,
        )

        wf_ids = {po.order_workflow_id for po in pos if po.order_workflow_id}
        terminal_by_wf: dict[int, int] = {}
        if wf_ids:
            wfs = (
                db.query(OrderWorkflow)
                .filter(
                    OrderWorkflow.workspace_id == workspace_id,
                    OrderWorkflow.id.in_(wf_ids),
                )
                .all()
            )
            for wf in wfs:
                seq = wf.status_sequence or []
                if isinstance(seq, list) and len(seq) > 0:
                    last = seq[-1]
                    if isinstance(last, int):
                        terminal_by_wf[wf.id] = last

        rows: List[ActiveOrderRow] = []

        for po in pos:
            if po.order_workflow_id:
                last_id = terminal_by_wf.get(po.order_workflow_id)
                if last_id is not None and po.current_status_id == last_id:
                    continue
            st = po.current_status
            rows.append(
                ActiveOrderRow(
                    order_kind="purchase",
                    id=po.id,
                    number=po.po_number,
                    summary=po.description or po.order_note,
                    current_status_id=po.current_status_id,
                    status_name=st.name if st else None,
                    created_at=po.created_at,
                    total_amount=po.total_amount,
                )
            )

        for to in tos:
            st = to.current_status
            rows.append(
                ActiveOrderRow(
                    order_kind="transfer",
                    id=to.id,
                    number=to.transfer_number,
                    summary=to.description or to.note,
                    current_status_id=to.current_status_id,
                    status_name=st.name if st else None,
                    created_at=to.created_at,
                    total_amount=None,
                )
            )

        rows.sort(key=lambda r: r.created_at, reverse=True)
        return rows

    def delete_purchase_order(self, db: Session, po_id: int, workspace_id: int) -> None:
        try:
            self.manager.delete_purchase_order(db, po_id=po_id, workspace_id=workspace_id)
            self._commit_transaction(db)
        except Exception:
            self._rollback_transaction(db)
            raise

    # ─── Items ─────────────────────────────────────────────────
    def add_item(
        self, db: Session, po_id: int, item_in: PurchaseOrderItemCreate,
        workspace_id: int, user_id: Optional[int] = None
    ) -> PurchaseOrderItem:
        try:
            record = self.manager.add_item(
                db, po_id=po_id, data=item_in, workspace_id=workspace_id, user_id=user_id
            )
            po = self.manager.get_purchase_order(db, po_id, workspace_id)
            if user_id is not None:
                self._sync_draft_invoice_for_po(db, po, workspace_id, user_id)
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except IntegrityError as exc:
            self._rollback_transaction(db)
            self._handle_item_integrity_error(exc)
        except HTTPException:
            self._rollback_transaction(db)
            raise
        except Exception:
            self._rollback_transaction(db)
            raise

    def update_item(
        self, db: Session, item_id: int, item_in: PurchaseOrderItemUpdate,
        workspace_id: int, user_id: Optional[int] = None
    ) -> PurchaseOrderItem:
        try:
            record = self.manager.update_item(
                db, item_id=item_id, data=item_in, workspace_id=workspace_id, user_id=user_id
            )
            if user_id is not None:
                po = self.manager.get_purchase_order(db, record.purchase_order_id, workspace_id)
                self._sync_draft_invoice_for_po(db, po, workspace_id, user_id)
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except IntegrityError as exc:
            self._rollback_transaction(db)
            self._handle_item_integrity_error(exc)
        except HTTPException:
            self._rollback_transaction(db)
            raise
        except Exception:
            self._rollback_transaction(db)
            raise

    def remove_item(
        self, db: Session, item_id: int, workspace_id: int, user_id: Optional[int] = None
    ) -> PurchaseOrderItem:
        try:
            record = self.manager.remove_item(
                db, item_id=item_id, workspace_id=workspace_id, user_id=user_id
            )
            if user_id is not None:
                po = self.manager.get_purchase_order(db, record.purchase_order_id, workspace_id)
                self._sync_draft_invoice_for_po(db, po, workspace_id, user_id)
            self._commit_transaction(db)
            return record
        except IntegrityError as exc:
            self._rollback_transaction(db)
            self._handle_item_integrity_error(exc)
        except HTTPException:
            self._rollback_transaction(db)
            raise
        except Exception:
            self._rollback_transaction(db)
            raise

    def sync_items(
        self,
        db: Session,
        po_id: int,
        sync_in: PurchaseOrderItemSyncRequest,
        workspace_id: int,
        user_id: Optional[int] = None,
    ) -> PurchaseOrder:
        try:
            po = self.manager.sync_items(
                db, po_id=po_id, data=sync_in, workspace_id=workspace_id, user_id=user_id
            )
            self._commit_transaction(db)
            db.refresh(po)
        except IntegrityError as exc:
            self._rollback_transaction(db)
            self._handle_item_integrity_error(exc, phase='items')
        except HTTPException:
            self._rollback_transaction(db)
            raise
        except Exception:
            self._rollback_transaction(db)
            raise

        if user_id is not None and po.account_id is not None:
            try:
                self._sync_draft_invoice_for_po(db, po, workspace_id, user_id)
                self._commit_transaction(db)
                db.refresh(po)
            except IntegrityError as exc:
                self._rollback_transaction(db)
                self._handle_item_integrity_error(exc, phase='invoice')
            except HTTPException:
                self._rollback_transaction(db)
                raise
            except Exception:
                self._rollback_transaction(db)
                raise

        return po

    def get_items(self, db: Session, po_id: int, workspace_id: int) -> List[PurchaseOrderItem]:
        return self.manager.get_items(db, po_id, workspace_id)

    # ─── Events ────────────────────────────────────────────────
    def list_events(self, db: Session, po_id: int, workspace_id: int):
        return self.manager.list_events(db, po_id=po_id, workspace_id=workspace_id)

    # ─── Approvers ─────────────────────────────────────────────
    def list_approvers(self, db: Session, po_id: int, workspace_id: int):
        return self.manager.list_approvers(db, po_id=po_id, workspace_id=workspace_id)

    def approval_summary_for(self, db: Session, po_id: int, workspace_id: int):
        po = self.manager.get_purchase_order(db, po_id=po_id, workspace_id=workspace_id)
        return self.manager.approval_summary(db, po)

    def add_approver(self, db: Session, po_id: int, user_id: int, workspace_id: int, assigned_by: int):
        try:
            record = self.manager.add_approver(
                db, po_id=po_id, user_id=user_id, workspace_id=workspace_id, assigned_by=assigned_by
            )
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    def remove_approver(
        self, db: Session, po_id: int, user_id: int, workspace_id: int, performed_by: Optional[int] = None
    ) -> None:
        try:
            self.manager.remove_approver(
                db, po_id=po_id, user_id=user_id, workspace_id=workspace_id, performed_by=performed_by
            )
            self._commit_transaction(db)
        except Exception:
            self._rollback_transaction(db)
            raise

    def set_approval(self, db: Session, po_id: int, user_id: int, workspace_id: int, approved: bool):
        try:
            record = self.manager.set_approval(
                db, po_id=po_id, user_id=user_id, workspace_id=workspace_id, approved=approved
            )
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    def create_invoice_for_purchase_order(
        self, db: Session, po_id: int, workspace_id: int, user_id: int
    ) -> PurchaseOrder:
        """Ensure the PO has a synced draft invoice (idempotent backfill)."""
        try:
            po = self.manager.get_purchase_order(db, po_id=po_id, workspace_id=workspace_id)
            self._sync_draft_invoice_for_po(db, po, workspace_id, user_id)
            if po.account_id is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail='Assign a supplier before a draft invoice can be created',
                )
            if po.invoice_id is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail='Could not create draft invoice for this purchase order',
                )
            self._commit_transaction(db)
            db.refresh(po)
            return po
        except IntegrityError as exc:
            self._rollback_transaction(db)
            self._handle_item_integrity_error(exc, phase='invoice')
        except HTTPException:
            self._rollback_transaction(db)
            raise
        except Exception:
            self._rollback_transaction(db)
            raise


purchase_order_service = PurchaseOrderService()
