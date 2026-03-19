"""Production Formula Service for orchestrating production formula workflows"""
from typing import List, Optional
from sqlalchemy.orm import Session
from app.services.base_service import BaseService
from app.managers.production_formula_manager import production_formula_manager
from app.models.production_formula import ProductionFormula
from app.models.production_formula_item import ProductionFormulaItem
from app.core.exceptions import NotFoundError, BusinessRuleError


class ProductionFormulaService(BaseService):
    """
    Service for Production Formula workflows.

    Handles:
    - Transaction boundaries (commit/rollback)
    - Formula and formula item CRUD
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
        workspace_id: int
    ) -> None:
        """Soft delete a production formula."""
        try:
            self.formula_manager.delete_formula(
                session=db,
                formula_id=formula_id,
                workspace_id=workspace_id
            )
            self._commit_transaction(db)
        except ValueError as e:
            self._rollback_transaction(db)
            raise NotFoundError(str(e))
        except Exception:
            self._rollback_transaction(db)
            raise

    # ─── Formula Item Operations ────────────────────────────────────

    def add_formula_item(
        self,
        db: Session,
        item_in: "ProductionFormulaItemCreate",
        workspace_id: int
    ) -> ProductionFormulaItem:
        """Add an item to a formula."""
        try:
            formula_item = self.formula_manager.add_formula_item(
                session=db,
                item_data=item_in,
                workspace_id=workspace_id
            )
            self._commit_transaction(db)
            db.refresh(formula_item)
            return formula_item
        except ValueError as e:
            self._rollback_transaction(db)
            error_msg = str(e)
            if "not found" in error_msg:
                raise NotFoundError(error_msg)
            raise BusinessRuleError(error_msg)
        except Exception:
            self._rollback_transaction(db)
            raise

    def update_formula_item(
        self,
        db: Session,
        formula_item_id: int,
        item_in: "ProductionFormulaItemUpdate",
        workspace_id: int
    ) -> ProductionFormulaItem:
        """Update a formula item."""
        try:
            formula_item = self.formula_manager.update_formula_item(
                session=db,
                formula_item_id=formula_item_id,
                item_data=item_in,
                workspace_id=workspace_id
            )
            self._commit_transaction(db)
            db.refresh(formula_item)
            return formula_item
        except ValueError as e:
            self._rollback_transaction(db)
            error_msg = str(e)
            if "not found" in error_msg:
                raise NotFoundError(error_msg)
            raise BusinessRuleError(error_msg)
        except Exception:
            self._rollback_transaction(db)
            raise

    def remove_formula_item(
        self,
        db: Session,
        formula_item_id: int,
        workspace_id: int
    ) -> None:
        """Remove an item from a formula (hard delete)."""
        try:
            self.formula_manager.remove_formula_item(
                session=db,
                formula_item_id=formula_item_id,
                workspace_id=workspace_id
            )
            self._commit_transaction(db)
        except ValueError as e:
            self._rollback_transaction(db)
            raise NotFoundError(str(e))
        except Exception:
            self._rollback_transaction(db)
            raise

    def get_formula_items(
        self,
        db: Session,
        formula_id: int,
        workspace_id: int,
        item_role: Optional[str] = None
    ) -> List[ProductionFormulaItem]:
        """Get items for a formula with optional role filter."""
        try:
            return self.formula_manager.get_formula_items(
                session=db,
                formula_id=formula_id,
                workspace_id=workspace_id,
                item_role=item_role
            )
        except ValueError as e:
            error_msg = str(e)
            if "not found" in error_msg:
                raise NotFoundError(error_msg)
            raise BusinessRuleError(error_msg)


# Singleton instance
production_formula_service = ProductionFormulaService()
