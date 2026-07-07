"""Work order event DAO. SECURITY: All queries MUST filter by workspace_id."""
from typing import List
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.dao.base import BaseDAO
from app.models.work_order_event import WorkOrderEvent


class WorkOrderEventDAO(BaseDAO[WorkOrderEvent, object, object]):
    def get_by_order(
        self, db: Session, *, work_order_id: int, workspace_id: int
    ) -> List[WorkOrderEvent]:
        return (
            db.query(WorkOrderEvent)
            .filter(
                WorkOrderEvent.work_order_id == work_order_id,
                WorkOrderEvent.workspace_id == workspace_id,
            )
            .order_by(desc(WorkOrderEvent.created_at), desc(WorkOrderEvent.id))
            .all()
        )


work_order_event_dao = WorkOrderEventDAO(WorkOrderEvent)
