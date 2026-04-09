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
from app.schemas.purchase_order import (
    PurchaseOrderCreate, PurchaseOrderUpdate,
    PurchaseOrderItemCreate, PurchaseOrderItemUpdate,
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
