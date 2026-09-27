"""Production Formula Stage DAO"""

from sqlalchemy.orm import Session

from app.dao.base import BaseDAO
from app.models.production_formula_stage import ProductionFormulaStage
from app.schemas.production_formula_stage import (
    ProductionFormulaStageCreate,
    ProductionFormulaStageUpdate,
)


class ProductionFormulaStageDAO(
    BaseDAO[ProductionFormulaStage, ProductionFormulaStageCreate, ProductionFormulaStageUpdate]
):
    def get_by_formula(
        self, db: Session, *, formula_id: int, workspace_id: int
    ) -> list[ProductionFormulaStage]:
        return (
            db.query(ProductionFormulaStage)
            .filter(
                ProductionFormulaStage.workspace_id == workspace_id,
                ProductionFormulaStage.formula_id == formula_id,
            )
            .order_by(ProductionFormulaStage.stage_order.asc())
            .all()
        )

    def get_by_id_and_workspace(
        self, db: Session, *, id: int, workspace_id: int
    ) -> ProductionFormulaStage | None:
        return (
            db.query(ProductionFormulaStage)
            .filter(ProductionFormulaStage.id == id, ProductionFormulaStage.workspace_id == workspace_id)
            .first()
        )

production_formula_stage_dao = ProductionFormulaStageDAO(ProductionFormulaStage)
