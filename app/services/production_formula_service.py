"""Production Formula Service for orchestrating production formula workflows"""
from typing import List, Optional
from sqlalchemy.orm import Session
from app.services.base_service import BaseService
from app.managers.production_formula_manager import production_formula_manager
from app.models.production_formula import ProductionFormula
from app.schemas.production_formula import ProductionFormulaCopy
from app.models.production_formula_stage_item import ProductionFormulaStageItem
from app.models.production_formula_stage_parameter import ProductionFormulaStageParameter
from app.core.exceptions import NotFoundError, BusinessRuleError


class ProductionFormulaService(BaseService):
    """
    Service for Production Formula workflows.

    Handles:
    - Transaction boundaries (commit/rollback)
    - Formula and path-stage CRUD
    - Error handling and exception translation
    """

    def __init__(self):
        super().__init__()
        self.formula_manager = production_formula_manager

    # ─── Formula Operations ─────────────────────────────────────────

    def create_formula(
        self,
        db: Session,
        formula_in: "ProductionFormulaCreate",
        workspace_id: int,
        user_id: int
    ) -> ProductionFormula:
        """Create a new production formula."""
        try:
            formula = self.formula_manager.create_formula(
                session=db,
                formula_data=formula_in,
                workspace_id=workspace_id,
                user_id=user_id
            )
            self._commit_transaction(db)
            db.refresh(formula)
            return formula
        except ValueError as e:
            self._rollback_transaction(db)
            raise BusinessRuleError(str(e))
        except Exception:
            self._rollback_transaction(db)
            raise

    def get_formula(
        self,
        db: Session,
        formula_id: int,
        workspace_id: int
    ) -> ProductionFormula:
        """Get formula by ID. Raises NotFoundError if not found."""
        formula = self.formula_manager.get_formula(db, formula_id, workspace_id)
        if not formula:
            raise NotFoundError(f"Production formula with ID {formula_id} not found")
        return formula

    def get_formulas(
        self,
        db: Session,
        workspace_id: int,
        active_only: bool = False,
        skip: int = 0,
        limit: int = 100
    ) -> List[ProductionFormula]:
        """Get formulas with optional filtering."""
        return self.formula_manager.get_formulas(
            session=db,
            workspace_id=workspace_id,
            active_only=active_only,
            skip=skip,
            limit=limit
        )

    def update_formula(
        self,
        db: Session,
        formula_id: int,
        formula_in: "ProductionFormulaUpdate",
        workspace_id: int,
        user_id: int
    ) -> ProductionFormula:
        """Update an existing production formula."""
        try:
            formula = self.formula_manager.update_formula(
                session=db,
                formula_id=formula_id,
                formula_data=formula_in,
                workspace_id=workspace_id,
                user_id=user_id
            )
            self._commit_transaction(db)
            db.refresh(formula)
            return formula
        except ValueError as e:
            self._rollback_transaction(db)
            error_msg = str(e)
            if "not found" in error_msg:
                raise NotFoundError(error_msg)
            raise BusinessRuleError(error_msg)
        except Exception:
            self._rollback_transaction(db)
            raise

    def delete_formula(
        self,
        db: Session,
        formula_id: int,
        workspace_id: int,
        user_id: int
    ) -> None:
        """Soft delete a production formula."""
        try:
            self.formula_manager.delete_formula(
                session=db,
                formula_id=formula_id,
                workspace_id=workspace_id,
                user_id=user_id
            )
            self._commit_transaction(db)
        except ValueError as e:
            self._rollback_transaction(db)
            raise NotFoundError(str(e))
        except Exception:
            self._rollback_transaction(db)
            raise

    # ─── Formula Stage Operations ───────────────────────────────────

    def get_formula_stages(
        self, db: Session, formula_id: int, workspace_id: int
    ) -> List["ProductionFormulaStage"]:
        try:
            return self.formula_manager.get_formula_stages(db, formula_id, workspace_id)
        except ValueError as e:
            raise NotFoundError(str(e))

    def duplicate_formula(
        self,
        db: Session,
        source_formula_id: int,
        copy_in: "ProductionFormulaCopy",
        workspace_id: int,
        user_id: int,
    ) -> ProductionFormula:
        try:
            formula = self.formula_manager.duplicate_formula(
                session=db,
                source_formula_id=source_formula_id,
                formula_code=copy_in.formula_code,
                name=copy_in.name,
                description=copy_in.description,
                factory_id=copy_in.factory_id,
                workspace_id=workspace_id,
                user_id=user_id,
                steps=copy_in.steps,
            )
            self._commit_transaction(db)
            db.refresh(formula)
            return formula
        except ValueError as e:
            self._rollback_transaction(db)
            error_msg = str(e)
            if "not found" in error_msg:
                raise NotFoundError(error_msg)
            raise BusinessRuleError(error_msg)
        except Exception:
            self._rollback_transaction(db)
            raise

    def append_line_step(
        self,
        db: Session,
        formula_id: int,
        production_line_id: int,
        workspace_id: int,
        user_id: int,
        name: Optional[str] = None,
        factory_id: Optional[int] = None,
    ):
        try:
            stage = self.formula_manager.append_line_step(
                db,
                formula_id,
                production_line_id,
                workspace_id,
                user_id,
                name=name,
                factory_id=factory_id,
            )
            self._commit_transaction(db)
            db.refresh(stage)
            return stage
        except ValueError as e:
            self._rollback_transaction(db)
            error_msg = str(e)
            if "not found" in error_msg:
                raise NotFoundError(error_msg)
            raise BusinessRuleError(error_msg)
        except Exception:
            self._rollback_transaction(db)
            raise

    def add_formula_stage(
        self, db: Session, stage_in: "ProductionFormulaStageCreate", workspace_id: int
    ) -> "ProductionFormulaStage":
        try:
            stage = self.formula_manager.add_formula_stage(db, stage_in, workspace_id)
            self._commit_transaction(db)
            db.refresh(stage)
            return stage
        except ValueError as e:
            self._rollback_transaction(db)
            error_msg = str(e)
            if "not found" in error_msg:
                raise NotFoundError(error_msg)
            raise BusinessRuleError(error_msg)
        except Exception:
            self._rollback_transaction(db)
            raise

    def update_formula_stage(
        self,
        db: Session,
        stage_id: int,
        stage_in: "ProductionFormulaStageUpdate",
        workspace_id: int,
    ) -> "ProductionFormulaStage":
        try:
            stage = self.formula_manager.update_formula_stage(db, stage_id, stage_in, workspace_id)
            self._commit_transaction(db)
            db.refresh(stage)
            return stage
        except ValueError as e:
            self._rollback_transaction(db)
            error_msg = str(e)
            if "not found" in error_msg:
                raise NotFoundError(error_msg)
            raise BusinessRuleError(error_msg)
        except Exception:
            self._rollback_transaction(db)
            raise

    def remove_formula_stage(self, db: Session, stage_id: int, workspace_id: int) -> None:
        try:
            self.formula_manager.remove_formula_stage(db, stage_id, workspace_id)
            self._commit_transaction(db)
        except ValueError as e:
            self._rollback_transaction(db)
            error_msg = str(e)
            if "not found" in error_msg:
                raise NotFoundError(error_msg)
            raise BusinessRuleError(error_msg)
        except Exception:
            self._rollback_transaction(db)
            raise


    # ─── Formula stage item operations ───────────────────────────────

    def get_formula_stage_items(
        self,
        db: Session,
        formula_id: int,
        stage_id: int,
        workspace_id: int,
        item_role: Optional[str] = None,
    ) -> List[ProductionFormulaStageItem]:
        try:
            return self.formula_manager.get_formula_stage_items(
                db, formula_id, stage_id, workspace_id, item_role=item_role
            )
        except ValueError as e:
            error_msg = str(e)
            if "not found" in error_msg:
                raise NotFoundError(error_msg)
            raise BusinessRuleError(error_msg)

    def get_all_formula_stage_items(
        self, db: Session, formula_id: int, workspace_id: int
    ) -> List[ProductionFormulaStageItem]:
        try:
            return self.formula_manager.get_all_formula_stage_items(db, formula_id, workspace_id)
        except ValueError as e:
            raise NotFoundError(str(e))

    def ensure_input_handoff_from_previous_stage(
        self, db: Session, formula_id: int, stage_id: int, workspace_id: int
    ) -> None:
        try:
            self.formula_manager.ensure_input_handoff_from_previous_stage(
                db, formula_id, stage_id, workspace_id
            )
            self._commit_transaction(db)
        except ValueError as e:
            self._rollback_transaction(db)
            error_msg = str(e)
            if "not found" in error_msg:
                raise NotFoundError(error_msg)
            raise BusinessRuleError(error_msg)
        except Exception:
            self._rollback_transaction(db)
            raise

    def add_formula_stage_item(
        self,
        db: Session,
        formula_id: int,
        stage_id: int,
        item_in: "ProductionFormulaStageItemCreate",
        workspace_id: int,
        user_id: int | None = None,
    ) -> ProductionFormulaStageItem:
        try:
            item = self.formula_manager.add_formula_stage_item(
                db, formula_id, stage_id, item_in, workspace_id, user_id=user_id
            )
            self._commit_transaction(db)
            db.refresh(item)
            return item
        except ValueError as e:
            self._rollback_transaction(db)
            error_msg = str(e)
            if "not found" in error_msg:
                raise NotFoundError(error_msg)
            raise BusinessRuleError(error_msg)
        except Exception:
            self._rollback_transaction(db)
            raise

    def update_formula_stage_item(
        self,
        db: Session,
        stage_item_id: int,
        item_in: "ProductionFormulaStageItemUpdate",
        workspace_id: int,
    ) -> ProductionFormulaStageItem:
        try:
            item = self.formula_manager.update_formula_stage_item(
                db, stage_item_id, item_in, workspace_id
            )
            self._commit_transaction(db)
            db.refresh(item)
            return item
        except ValueError as e:
            self._rollback_transaction(db)
            error_msg = str(e)
            if "not found" in error_msg:
                raise NotFoundError(error_msg)
            raise BusinessRuleError(error_msg)
        except Exception:
            self._rollback_transaction(db)
            raise

    def remove_formula_stage_item(
        self, db: Session, stage_item_id: int, workspace_id: int
    ) -> None:
        try:
            self.formula_manager.remove_formula_stage_item(db, stage_item_id, workspace_id)
            self._commit_transaction(db)
        except ValueError as e:
            self._rollback_transaction(db)
            raise NotFoundError(str(e))
        except Exception:
            self._rollback_transaction(db)
            raise

    # ─── Formula stage parameter operations ──────────────────────────

    def get_formula_stage_parameters(
        self, db: Session, formula_id: int, stage_id: int, workspace_id: int
    ) -> List[ProductionFormulaStageParameter]:
        try:
            return self.formula_manager.get_formula_stage_parameters(
                db, formula_id, stage_id, workspace_id
            )
        except ValueError as e:
            error_msg = str(e)
            if "not found" in error_msg:
                raise NotFoundError(error_msg)
            raise BusinessRuleError(error_msg)

    def get_all_formula_stage_parameters(
        self, db: Session, formula_id: int, workspace_id: int
    ) -> List[ProductionFormulaStageParameter]:
        try:
            return self.formula_manager.get_all_formula_stage_parameters(
                db, formula_id, workspace_id
            )
        except ValueError as e:
            raise NotFoundError(str(e))

    def add_formula_stage_parameter(
        self,
        db: Session,
        formula_id: int,
        stage_id: int,
        param_in: "ProductionFormulaStageParameterCreate",
        workspace_id: int,
    ) -> ProductionFormulaStageParameter:
        try:
            param = self.formula_manager.add_formula_stage_parameter(
                db, formula_id, stage_id, param_in, workspace_id
            )
            self._commit_transaction(db)
            db.refresh(param)
            return param
        except ValueError as e:
            self._rollback_transaction(db)
            error_msg = str(e)
            if "not found" in error_msg:
                raise NotFoundError(error_msg)
            raise BusinessRuleError(error_msg)
        except Exception:
            self._rollback_transaction(db)
            raise

    def update_formula_stage_parameter(
        self,
        db: Session,
        parameter_id: int,
        param_in: "ProductionFormulaStageParameterUpdate",
        workspace_id: int,
    ) -> ProductionFormulaStageParameter:
        try:
            param = self.formula_manager.update_formula_stage_parameter(
                db, parameter_id, param_in, workspace_id
            )
            self._commit_transaction(db)
            db.refresh(param)
            return param
        except ValueError as e:
            self._rollback_transaction(db)
            error_msg = str(e)
            if "not found" in error_msg:
                raise NotFoundError(error_msg)
            raise BusinessRuleError(error_msg)
        except Exception:
            self._rollback_transaction(db)
            raise

    def remove_formula_stage_parameter(
        self, db: Session, parameter_id: int, workspace_id: int
    ) -> None:
        try:
            self.formula_manager.remove_formula_stage_parameter(
                db, parameter_id, workspace_id
            )
            self._commit_transaction(db)
        except ValueError as e:
            self._rollback_transaction(db)
            raise NotFoundError(str(e))
        except Exception:
            self._rollback_transaction(db)
            raise


# Singleton instance
production_formula_service = ProductionFormulaService()
