"""Purchase Order Service - transaction orchestration"""
from datetime import date
from decimal import Decimal
from typing import List, Optional
from sqlalchemy.orm import Session
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
    ActiveOrderRow,
)
from app.schemas.account_invoice import AccountInvoiceCreate


class PurchaseOrderService(BaseService):
    """Service for purchase order workflows. Handles commit/rollback."""

    def __init__(self):
        super().__init__()
        self.manager = purchase_order_manager
        self.account_invoice_manager = account_invoice_manager

    def create_purchase_order(
        self, db: Session, po_in: PurchaseOrderCreate,
        workspace_id: int, user_id: int
    ) -> PurchaseOrder:
        try:
            record = self.manager.create_purchase_order(db, data=po_in, workspace_id=workspace_id, user_id=user_id)
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    def update_purchase_order(
        self, db: Session, po_id: int, po_in: PurchaseOrderUpdate,
        workspace_id: int, user_id: int
    ) -> PurchaseOrder:
        try:
            record = self.manager.update_purchase_order(db, po_id=po_id, data=po_in, workspace_id=workspace_id, user_id=user_id)
            self._commit_transaction(db)
            db.refresh(record)
            return record
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
        workspace_id: int
    ) -> PurchaseOrderItem:
        try:
            record = self.manager.add_item(db, po_id=po_id, data=item_in, workspace_id=workspace_id)
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    def update_item(
        self, db: Session, item_id: int, item_in: PurchaseOrderItemUpdate,
        workspace_id: int
    ) -> PurchaseOrderItem:
        try:
            record = self.manager.update_item(db, item_id=item_id, data=item_in, workspace_id=workspace_id)
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    def remove_item(self, db: Session, item_id: int, workspace_id: int) -> PurchaseOrderItem:
        try:
            record = self.manager.remove_item(db, item_id=item_id, workspace_id=workspace_id)
            self._commit_transaction(db)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    def get_items(self, db: Session, po_id: int, workspace_id: int) -> List[PurchaseOrderItem]:
        return self.manager.get_items(db, po_id, workspace_id)

    def create_invoice_for_purchase_order(
        self, db: Session, po_id: int, workspace_id: int, user_id: int
    ) -> PurchaseOrder:
        """
        Create exactly one payable account invoice from a purchase order.

        Rules:
        - One order -> one invoice
        - Account is required
        """
        try:
            po = self.manager.get_purchase_order(db, po_id=po_id, workspace_id=workspace_id)

            if po.invoice_id is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Invoice already exists for this purchase order"
                )

            if po.account_id is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Cannot create invoice: purchase order has no account selected"
                )

            invoice_in = AccountInvoiceCreate(
                account_id=po.account_id,
                order_id=None,  # Legacy orders FK; keep null for split order tables
                invoice_type="payable",
                invoice_amount=Decimal(str(po.total_amount or 0)),
                invoice_number=None,
                vendor_invoice_number=None,
                invoice_date=date.today(),
                due_date=None,
                description=f"Auto-created from purchase order {po.po_number}",
                notes=po.order_note or po.description,
                allow_payments=True,
                payment_locked_reason=None
            )

            try:
                invoice = self.account_invoice_manager.create_invoice(
                    session=db,
                    invoice_data=invoice_in,
                    workspace_id=workspace_id,
                    user_id=user_id
                )
            except HTTPException as exc:
                # Surface a clearer message in this order workflow context.
                if exc.status_code == status.HTTP_404_NOT_FOUND:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail="Cannot create invoice: selected account was not found in this workspace"
                    ) from exc
                raise
            po.invoice_id = invoice.id
            db.flush()
            self._commit_transaction(db)
            db.refresh(po)
            return po
        except Exception:
            self._rollback_transaction(db)
            raise


purchase_order_service = PurchaseOrderService()
