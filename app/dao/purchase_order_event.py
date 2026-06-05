"""Purchase order event DAO. SECURITY: All queries MUST filter by workspace_id."""
from typing import List
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.dao.base import BaseDAO
from app.models.purchase_order_event import PurchaseOrderEvent
from app.schemas.purchase_order import PurchaseOrderEventResponse


class PurchaseOrderEventDAO(BaseDAO[PurchaseOrderEvent, PurchaseOrderEventResponse, PurchaseOrderEventResponse]):
    def get_by_order(
        self, db: Session, *, purchase_order_id: int, workspace_id: int
    ) -> List[PurchaseOrderEvent]:
        return (
            db.query(PurchaseOrderEvent)
            .filter(
                PurchaseOrderEvent.purchase_order_id == purchase_order_id,
                PurchaseOrderEvent.workspace_id == workspace_id,
            )
            .order_by(desc(PurchaseOrderEvent.created_at), desc(PurchaseOrderEvent.id))
            .all()
        )


purchase_order_event_dao = PurchaseOrderEventDAO(PurchaseOrderEvent)
