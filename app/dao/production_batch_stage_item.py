"""DAO for per-step batch material rows."""
from typing import List, Optional

from sqlalchemy.orm import Session

from app.dao.base import BaseDAO
from app.models.production_batch_stage_item import ProductionBatchStageItem
from app.schemas.production_batch_stage_item import ProductionBatchStageItemUpdate


class ProductionBatchStageItemDAO(
    BaseDAO[ProductionBatchStageItem, dict, ProductionBatchStageItemUpdate]
):
    def get_by_batch(
        self, db: Session, *, batch_id: int, workspace_id: int
    ) -> List[ProductionBatchStageItem]:
        return (
            db.query(ProductionBatchStageItem)
            .filter(
                ProductionBatchStageItem.workspace_id == workspace_id,
                ProductionBatchStageItem.batch_id == batch_id,
            )
            .order_by(
                ProductionBatchStageItem.batch_stage_log_id.asc(),
                ProductionBatchStageItem.id.asc(),
            )
            .all()
        )

    def get_by_stage_log(
        self, db: Session, *, batch_stage_log_id: int, workspace_id: int
    ) -> List[ProductionBatchStageItem]:
        return (
            db.query(ProductionBatchStageItem)
            .filter(
                ProductionBatchStageItem.workspace_id == workspace_id,
                ProductionBatchStageItem.batch_stage_log_id == batch_stage_log_id,
            )
            .order_by(ProductionBatchStageItem.id.asc())
            .all()
        )

    def get_by_id_and_workspace(
        self, db: Session, *, id: int, workspace_id: int
    ) -> Optional[ProductionBatchStageItem]:
        return (
            db.query(ProductionBatchStageItem)
            .filter(
                ProductionBatchStageItem.id == id,
                ProductionBatchStageItem.workspace_id == workspace_id,
            )
            .first()
        )


production_batch_stage_item_dao = ProductionBatchStageItemDAO(ProductionBatchStageItem)
