"""Production batch stage parameter DAO."""
from typing import List, Optional

from sqlalchemy.orm import Session

from app.dao.base import BaseDAO
from app.models.production_batch_stage_parameter import ProductionBatchStageParameter
from app.schemas.production_batch_stage_parameter import ProductionBatchStageParameterUpdate


class ProductionBatchStageParameterDAO(
    BaseDAO[
        ProductionBatchStageParameter,
        dict,
        ProductionBatchStageParameterUpdate,
    ]
):
    def get_by_batch_ids(
        self, db: Session, *, batch_ids: List[int], workspace_id: int
    ) -> List[ProductionBatchStageParameter]:
        if not batch_ids:
            return []
        return (
            db.query(ProductionBatchStageParameter)
            .filter(
                ProductionBatchStageParameter.workspace_id == workspace_id,
                ProductionBatchStageParameter.batch_id.in_(batch_ids),
            )
            .order_by(
                ProductionBatchStageParameter.batch_stage_log_id.asc(),
                ProductionBatchStageParameter.id.asc(),
            )
            .all()
        )

    def get_by_batch(
        self, db: Session, *, batch_id: int, workspace_id: int
    ) -> List[ProductionBatchStageParameter]:
        return (
            db.query(ProductionBatchStageParameter)
            .filter(
                ProductionBatchStageParameter.workspace_id == workspace_id,
                ProductionBatchStageParameter.batch_id == batch_id,
            )
            .order_by(
                ProductionBatchStageParameter.batch_stage_log_id.asc(),
                ProductionBatchStageParameter.id.asc(),
            )
            .all()
        )

    def get_by_stage_log(
        self, db: Session, *, batch_stage_log_id: int, workspace_id: int
    ) -> List[ProductionBatchStageParameter]:
        return (
            db.query(ProductionBatchStageParameter)
            .filter(
                ProductionBatchStageParameter.workspace_id == workspace_id,
                ProductionBatchStageParameter.batch_stage_log_id == batch_stage_log_id,
            )
            .order_by(ProductionBatchStageParameter.id.asc())
            .all()
        )

    def get_by_id_and_workspace(
        self, db: Session, *, id: int, workspace_id: int
    ) -> Optional[ProductionBatchStageParameter]:
        return (
            db.query(ProductionBatchStageParameter)
            .filter(
                ProductionBatchStageParameter.id == id,
                ProductionBatchStageParameter.workspace_id == workspace_id,
            )
            .first()
        )

    def get_by_stage_log_and_source(
        self,
        db: Session,
        *,
        batch_stage_log_id: int,
        source_parameter_id: int,
        workspace_id: int,
    ) -> Optional[ProductionBatchStageParameter]:
        return (
            db.query(ProductionBatchStageParameter)
            .filter(
                ProductionBatchStageParameter.workspace_id == workspace_id,
                ProductionBatchStageParameter.batch_stage_log_id == batch_stage_log_id,
                ProductionBatchStageParameter.source_parameter_id == source_parameter_id,
            )
            .first()
        )


production_batch_stage_parameter_dao = ProductionBatchStageParameterDAO(ProductionBatchStageParameter)

