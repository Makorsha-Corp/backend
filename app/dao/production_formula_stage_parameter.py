"""Production formula stage parameter DAO."""
from typing import List, Optional

from sqlalchemy.orm import Session

from app.dao.base import BaseDAO
from app.models.production_formula_stage import ProductionFormulaStage
from app.models.production_formula_stage_parameter import ProductionFormulaStageParameter
from app.schemas.production_formula_stage_parameter import (
    ProductionFormulaStageParameterCreate,
    ProductionFormulaStageParameterUpdate,
)


class ProductionFormulaStageParameterDAO(
    BaseDAO[
        ProductionFormulaStageParameter,
        ProductionFormulaStageParameterCreate,
        ProductionFormulaStageParameterUpdate,
    ]
):
    def get_by_stage(
        self, db: Session, *, formula_stage_id: int, workspace_id: int
    ) -> List[ProductionFormulaStageParameter]:
        return (
            db.query(ProductionFormulaStageParameter)
            .filter(
                ProductionFormulaStageParameter.workspace_id == workspace_id,
                ProductionFormulaStageParameter.formula_stage_id == formula_stage_id,
            )
            .order_by(
                ProductionFormulaStageParameter.sort_order.asc(),
                ProductionFormulaStageParameter.id.asc(),
            )
            .all()
        )

    def get_by_formula(
        self, db: Session, *, formula_id: int, workspace_id: int
    ) -> List[ProductionFormulaStageParameter]:
        return (
            db.query(ProductionFormulaStageParameter)
            .join(
                ProductionFormulaStage,
                ProductionFormulaStage.id == ProductionFormulaStageParameter.formula_stage_id,
            )
            .filter(
                ProductionFormulaStage.workspace_id == workspace_id,
                ProductionFormulaStage.formula_id == formula_id,
            )
            .order_by(
                ProductionFormulaStageParameter.formula_stage_id.asc(),
                ProductionFormulaStageParameter.sort_order.asc(),
                ProductionFormulaStageParameter.id.asc(),
            )
            .all()
        )

    def get_by_id_and_workspace(
        self, db: Session, *, id: int, workspace_id: int
    ) -> Optional[ProductionFormulaStageParameter]:
        return (
            db.query(ProductionFormulaStageParameter)
            .filter(
                ProductionFormulaStageParameter.id == id,
                ProductionFormulaStageParameter.workspace_id == workspace_id,
            )
            .first()
        )

    def label_exists_on_stage(
        self,
        db: Session,
        *,
        formula_stage_id: int,
        workspace_id: int,
        label: str,
        exclude_id: Optional[int] = None,
    ) -> bool:
        normalized = label.strip().casefold()
        rows = self.get_by_stage(db, formula_stage_id=formula_stage_id, workspace_id=workspace_id)
        for row in rows:
            if exclude_id is not None and row.id == exclude_id:
                continue
            if row.label.strip().casefold() == normalized:
                return True
        return False


production_formula_stage_parameter_dao = ProductionFormulaStageParameterDAO(
    ProductionFormulaStageParameter
)

