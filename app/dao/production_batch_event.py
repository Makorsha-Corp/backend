"""Production batch event DAO. SECURITY: filter by workspace_id."""
from typing import List

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.dao.base import BaseDAO
from app.models.production_batch_event import ProductionBatchEvent


class ProductionBatchEventDAO(BaseDAO[ProductionBatchEvent, object, object]):
    def get_by_batch(
        self,
        db: Session,
        *,
        batch_id: int,
        workspace_id: int,
        skip: int = 0,
        limit: int = 200,
    ) -> List[ProductionBatchEvent]:
        return (
            db.query(ProductionBatchEvent)
            .filter(
                ProductionBatchEvent.batch_id == batch_id,
                ProductionBatchEvent.workspace_id == workspace_id,
            )
            .order_by(desc(ProductionBatchEvent.created_at), desc(ProductionBatchEvent.id))
            .offset(skip)
            .limit(limit)
            .all()
        )


production_batch_event_dao = ProductionBatchEventDAO(ProductionBatchEvent)
