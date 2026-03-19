"""Transfer order DAO. SECURITY: All queries MUST filter by workspace_id."""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.dao.base import BaseDAO
from app.models.transfer_order import TransferOrder
from app.models.transfer_order_item import TransferOrderItem
from app.schemas.transfer_order import TransferOrderCreate, TransferOrderUpdate, TransferOrderItemCreate, TransferOrderItemUpdate


class TransferOrderDAO(BaseDAO[TransferOrder, TransferOrderCreate, TransferOrderUpdate]):
    def get_by_workspace(self, db: Session, *, workspace_id: int, skip: int = 0, limit: int = 100) -> List[TransferOrder]:
        query = db.query(TransferOrder).filter(TransferOrder.workspace_id == workspace_id)
        return query.order_by(desc(TransferOrder.created_at)).offset(skip).limit(limit).all()

    def get_by_id_and_workspace(self, db: Session, *, id: int, workspace_id: int) -> Optional[TransferOrder]:
        return db.query(TransferOrder).filter(TransferOrder.id == id, TransferOrder.workspace_id == workspace_id).first()

    def get_next_number(self, db: Session, *, workspace_id: int) -> str:
        from datetime import datetime
        year = datetime.now().year
        prefix = f"TR-{year}-"
        last = db.query(TransferOrder).filter(TransferOrder.workspace_id == workspace_id, TransferOrder.transfer_number.like(f"{prefix}%")).order_by(desc(TransferOrder.transfer_number)).first()
        if last:
            try:
                return f"{prefix}{int(last.transfer_number.split('-')[-1]) + 1:03d}"
            except (ValueError, IndexError):
                pass
        return f"{prefix}001"


class TransferOrderItemDAO(BaseDAO[TransferOrderItem, TransferOrderItemCreate, TransferOrderItemUpdate]):
    def get_by_order(self, db: Session, *, transfer_order_id: int, workspace_id: int) -> List[TransferOrderItem]:
        return db.query(TransferOrderItem).filter(TransferOrderItem.transfer_order_id == transfer_order_id, TransferOrderItem.workspace_id == workspace_id).order_by(TransferOrderItem.line_number).all()

    def get_by_id_and_workspace(self, db: Session, *, id: int, workspace_id: int) -> Optional[TransferOrderItem]:
        return db.query(TransferOrderItem).filter(TransferOrderItem.id == id, TransferOrderItem.workspace_id == workspace_id).first()


transfer_order_dao = TransferOrderDAO(TransferOrder)
transfer_order_item_dao = TransferOrderItemDAO(TransferOrderItem)
