"""Purchase order DAO. SECURITY: All queries MUST filter by workspace_id."""
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc
from app.dao.base import BaseDAO
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem
from app.schemas.purchase_order import PurchaseOrderCreate, PurchaseOrderUpdate, PurchaseOrderItemCreate, PurchaseOrderItemUpdate


class PurchaseOrderDAO(BaseDAO[PurchaseOrder, PurchaseOrderCreate, PurchaseOrderUpdate]):
    def get_by_workspace(
        self,
        db: Session,
        *,
        workspace_id: int,
        account_id: Optional[int] = None,
        invoice_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[PurchaseOrder]:
        query = (
            db.query(PurchaseOrder)
            .options(joinedload(PurchaseOrder.current_status))
            .filter(PurchaseOrder.workspace_id == workspace_id)
        )
        if account_id:
            query = query.filter(PurchaseOrder.account_id == account_id)
        if invoice_id is not None:
            query = query.filter(PurchaseOrder.invoice_id == invoice_id)
        return query.order_by(desc(PurchaseOrder.created_at)).offset(skip).limit(limit).all()

    def list_for_destination(
        self,
        db: Session,
        *,
        workspace_id: int,
        destination_type: str,
        destination_id: int,
    ) -> List[PurchaseOrder]:
        return (
            db.query(PurchaseOrder)
            .options(joinedload(PurchaseOrder.current_status))
            .filter(
                PurchaseOrder.workspace_id == workspace_id,
                PurchaseOrder.destination_type == destination_type,
                PurchaseOrder.destination_id == destination_id,
            )
            .order_by(desc(PurchaseOrder.created_at))
            .all()
        )

    def get_by_id_and_workspace(self, db: Session, *, id: int, workspace_id: int) -> Optional[PurchaseOrder]:
        return (
            db.query(PurchaseOrder)
            .options(joinedload(PurchaseOrder.current_status))
            .filter(PurchaseOrder.id == id, PurchaseOrder.workspace_id == workspace_id)
            .first()
        )

    def get_by_invoice_id(
        self, db: Session, *, invoice_id: int, workspace_id: int
    ) -> Optional[PurchaseOrder]:
        return (
            db.query(PurchaseOrder)
            .filter(
                PurchaseOrder.invoice_id == invoice_id,
                PurchaseOrder.workspace_id == workspace_id,
            )
            .first()
        )

    def get_next_number(self, db: Session, *, workspace_id: int) -> str:
        """Backward-compatible alias for allocate_po_number."""
        return self.allocate_po_number(db, workspace_id=workspace_id)

    def allocate_po_number(self, db: Session, *, workspace_id: int) -> str:
        """
        Next PO number for this workspace/year, skipping any po_number already
        taken globally (handles legacy global-unique constraint on po_number).
        """
        from datetime import datetime

        year = datetime.now().year
        prefix = f"PO-{year}-"

        rows = (
            db.query(PurchaseOrder.po_number)
            .filter(
                PurchaseOrder.workspace_id == workspace_id,
                PurchaseOrder.po_number.like(f"{prefix}%"),
            )
            .all()
        )
        max_seq = 0
        for (num,) in rows:
            try:
                max_seq = max(max_seq, int(str(num).rsplit("-", 1)[-1]))
            except ValueError:
                continue

        seq = max_seq + 1 if max_seq else 1
        for _ in range(1000):
            candidate = f"{prefix}{seq:03d}"
            taken = (
                db.query(PurchaseOrder.id)
                .filter(PurchaseOrder.po_number == candidate)
                .first()
            )
            if not taken:
                return candidate
            seq += 1

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not allocate a unique purchase order number",
        )


class PurchaseOrderItemDAO(BaseDAO[PurchaseOrderItem, PurchaseOrderItemCreate, PurchaseOrderItemUpdate]):
    def get_by_order(self, db: Session, *, purchase_order_id: int, workspace_id: int) -> List[PurchaseOrderItem]:
        return db.query(PurchaseOrderItem).filter(PurchaseOrderItem.purchase_order_id == purchase_order_id, PurchaseOrderItem.workspace_id == workspace_id).order_by(PurchaseOrderItem.line_number).all()

    def get_by_id_and_workspace(self, db: Session, *, id: int, workspace_id: int) -> Optional[PurchaseOrderItem]:
        return db.query(PurchaseOrderItem).filter(PurchaseOrderItem.id == id, PurchaseOrderItem.workspace_id == workspace_id).first()


purchase_order_dao = PurchaseOrderDAO(PurchaseOrder)
purchase_order_item_dao = PurchaseOrderItemDAO(PurchaseOrderItem)
