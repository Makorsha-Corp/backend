"""Transfer order event DAO. SECURITY: All queries MUST filter by workspace_id."""
from typing import List
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.dao.base import BaseDAO
from app.models.transfer_order_event import TransferOrderEvent


class TransferOrderEventDAO(BaseDAO[TransferOrderEvent, object, object]):
    def get_by_order(
        self, db: Session, *, transfer_order_id: int, workspace_id: int
    ) -> List[TransferOrderEvent]:
        return (
            db.query(TransferOrderEvent)
            .filter(
                TransferOrderEvent.transfer_order_id == transfer_order_id,
                TransferOrderEvent.workspace_id == workspace_id,
            )
            .order_by(desc(TransferOrderEvent.created_at), desc(TransferOrderEvent.id))
            .all()
        )


transfer_order_event_dao = TransferOrderEventDAO(TransferOrderEvent)
