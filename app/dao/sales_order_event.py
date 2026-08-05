"""Sales order event DAO. SECURITY: All queries MUST filter by workspace_id."""
from typing import List
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.dao.base import BaseDAO
from app.models.sales_order_event import SalesOrderEvent
from app.schemas.sales_order import SalesOrderEventResponse


class SalesOrderEventDAO(BaseDAO[SalesOrderEvent, SalesOrderEventResponse, SalesOrderEventResponse]):
    def get_by_order(
        self, db: Session, *, sales_order_id: int, workspace_id: int
    ) -> List[SalesOrderEvent]:
        return (
            db.query(SalesOrderEvent)
            .filter(
                SalesOrderEvent.sales_order_id == sales_order_id,
                SalesOrderEvent.workspace_id == workspace_id,
            )
            .order_by(desc(SalesOrderEvent.created_at), desc(SalesOrderEvent.id))
            .all()
        )


sales_order_event_dao = SalesOrderEventDAO(SalesOrderEvent)
