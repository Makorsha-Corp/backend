"""Production Batch Stage Log DAO"""
from typing import List, Optional
from sqlalchemy.orm import Session
from app.dao.base import BaseDAO
from app.models.production_batch_stage_log import ProductionBatchStageLog
from app.schemas.production_batch_stage_log import (
    ProductionBatchStageLogCreate,
    ProductionBatchStageLogUpdate,
)


class ProductionBatchStageLogDAO(
    BaseDAO[ProductionBatchStageLog, ProductionBatchStageLogCreate, ProductionBatchStageLogUpdate]
):
    def get_by_batch(
        self, db: Session, *, batch_id: int, workspace_id: int
    ) -> List[ProductionBatchStageLog]:
        return (
            db.query(ProductionBatchStageLog)
            .filter(
                ProductionBatchStageLog.workspace_id == workspace_id,
                ProductionBatchStageLog.batch_id == batch_id,
            )
            .order_by(ProductionBatchStageLog.stage_order.asc(), ProductionBatchStageLog.id.asc())
            .all()
        )

    def get_by_id_and_workspace(
        self, db: Session, *, id: int, workspace_id: int
    ) -> Optional[ProductionBatchStageLog]:
        return (
            db.query(ProductionBatchStageLog)
            .filter(ProductionBatchStageLog.id == id, ProductionBatchStageLog.workspace_id == workspace_id)
            .first()
        )


production_batch_stage_log_dao = ProductionBatchStageLogDAO(ProductionBatchStageLog)
