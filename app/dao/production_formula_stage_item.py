"""Production formula stage item DAO."""
from typing import List, Optional

from sqlalchemy.orm import Session

from app.dao.base import BaseDAO
from app.models.production_formula_stage import ProductionFormulaStage
from app.models.production_formula_stage_item import ProductionFormulaStageItem
from app.schemas.production_formula_stage_item import (
    ProductionFormulaStageItemCreate,
    ProductionFormulaStageItemUpdate,
)


class ProductionFormulaStageItemDAO(
    BaseDAO[ProductionFormulaStageItem, ProductionFormulaStageItemCreate, ProductionFormulaStageItemUpdate]
):
    def get_by_stage(
        self, db: Session, *, formula_stage_id: int, workspace_id: int, item_role: Optional[str] = None
    ) -> List[ProductionFormulaStageItem]:
        query = db.query(ProductionFormulaStageItem).filter(
            ProductionFormulaStageItem.workspace_id == workspace_id,
            ProductionFormulaStageItem.formula_stage_id == formula_stage_id,
        )
        if item_role is not None:
            query = query.filter(ProductionFormulaStageItem.item_role == item_role)
        return query.all()

    def get_by_formula(
        self, db: Session, *, formula_id: int, workspace_id: int
    ) -> List[ProductionFormulaStageItem]:
        return (
            db.query(ProductionFormulaStageItem)
            .join(
                ProductionFormulaStage,
                ProductionFormulaStage.id == ProductionFormulaStageItem.formula_stage_id,
            )
            .filter(
                ProductionFormulaStage.workspace_id == workspace_id,
                ProductionFormulaStage.formula_id == formula_id,
            )
            .all()
        )

    def get_by_id_and_workspace(
        self, db: Session, *, id: int, workspace_id: int
    ) -> Optional[ProductionFormulaStageItem]:
        return (
            db.query(ProductionFormulaStageItem)
            .filter(
                ProductionFormulaStageItem.id == id,
                ProductionFormulaStageItem.workspace_id == workspace_id,
            )
            .first()
        )


production_formula_stage_item_dao = ProductionFormulaStageItemDAO(ProductionFormulaStageItem)
