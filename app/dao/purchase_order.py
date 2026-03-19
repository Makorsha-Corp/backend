"""Purchase order DAO. SECURITY: All queries MUST filter by workspace_id."""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.dao.base import BaseDAO
from app.models.purchase_order import PurchaseOrder
from app.models.purchase_order_item import PurchaseOrderItem
from app.schemas.purchase_order import PurchaseOrderCreate, PurchaseOrderUpdate, PurchaseOrderItemCreate, PurchaseOrderItemUpdate


class PurchaseOrderDAO(BaseDAO[PurchaseOrder, PurchaseOrderCreate, PurchaseOrderUpdate]):
    def get_by_workspace(self, db: Session, *, workspace_id: int, account_id: Optional[int] = None, skip: int = 0, limit: int = 100) -> List[PurchaseOrder]:
        query = db.query(PurchaseOrder).filter(PurchaseOrder.workspace_id == workspace_id)
        if account_id:
            query = query.filter(PurchaseOrder.account_id == account_id)
        return query.order_by(desc(PurchaseOrder.created_at)).offset(skip).limit(limit).all()

    def get_by_id_and_workspace(self, db: Session, *, id: int, workspace_id: int) -> Optional[PurchaseOrder]:
        return db.query(PurchaseOrder).filter(PurchaseOrder.id == id, PurchaseOrder.workspace_id == workspace_id).first()

    def get_next_number(self, db: Session, *, workspace_id: int) -> str:
        from datetime import datetime
        year = datetime.now().year
        prefix = f"PO-{year}-"
        last = db.query(PurchaseOrder).filter(PurchaseOrder.workspace_id == workspace_id, PurchaseOrder.po_number.like(f"{prefix}%")).order_by(desc(PurchaseOrder.po_number)).first()
        if last:
            try:
                return f"{prefix}{int(last.po_number.split('-')[-1]) + 1:03d}"
            except (ValueError, IndexError):
                pass
        return f"{prefix}001"


class PurchaseOrderItemDAO(BaseDAO[PurchaseOrderItem, PurchaseOrderItemCreate, PurchaseOrderItemUpdate]):
    def get_by_order(self, db: Session, *, purchase_order_id: int, workspace_id: int) -> List[PurchaseOrderItem]:
        return db.query(PurchaseOrderItem).filter(PurchaseOrderItem.purchase_order_id == purchase_order_id, PurchaseOrderItem.workspace_id == workspace_id).order_by(PurchaseOrderItem.line_number).all()

    def get_by_id_and_workspace(self, db: Session, *, id: int, workspace_id: int) -> Optional[PurchaseOrderItem]:
        return db.query(PurchaseOrderItem).filter(PurchaseOrderItem.id == id, PurchaseOrderItem.workspace_id == workspace_id).first()


purchase_order_dao = PurchaseOrderDAO(PurchaseOrder)
purchase_order_item_dao = PurchaseOrderItemDAO(PurchaseOrderItem)
