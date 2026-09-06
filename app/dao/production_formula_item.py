"""Production Formula Item DAO operations"""
from typing import List, Optional
from sqlalchemy.orm import Session
from app.dao.base import BaseDAO
from app.models.production_formula_item import ProductionFormulaItem
from app.schemas.production_formula_item import ProductionFormulaItemCreate, ProductionFormulaItemUpdate


class ProductionFormulaItemDAO(BaseDAO[ProductionFormulaItem, ProductionFormulaItemCreate, ProductionFormulaItemUpdate]):
    """
    DAO operations for ProductionFormulaItem model.
    All methods enforce workspace isolation for security.
    """

    def get_by_formula(
        self, db: Session, *, formula_id: int, workspace_id: int
    ) -> List[ProductionFormulaItem]:
        """
        Get all items for a formula (SECURITY-CRITICAL)

        Args:
            db: Database session
            formula_id: Formula ID
            workspace_id: Workspace ID to filter by

        Returns:
            List of formula items
        """
        return (
            db.query(ProductionFormulaItem)
            .filter(
                ProductionFormulaItem.workspace_id == workspace_id,
                ProductionFormulaItem.formula_id == formula_id
            )
            .all()
        )

    def get_by_formula_and_role(
        self, db: Session, *, formula_id: int, item_role: str, workspace_id: int
    ) -> List[ProductionFormulaItem]:
        """
        Get items by formula and role (SECURITY-CRITICAL)

        Args:
            db: Database session
            formula_id: Formula ID
            item_role: Item role ('input', 'output', 'waste', 'byproduct')
            workspace_id: Workspace ID to filter by

        Returns:
            List of formula items
        """
        return (
            db.query(ProductionFormulaItem)
            .filter(
                ProductionFormulaItem.workspace_id == workspace_id,
                ProductionFormulaItem.formula_id == formula_id,
                ProductionFormulaItem.item_role == item_role
            )
            .all()
        )

    def get_by_id_and_workspace(
        self, db: Session, *, id: int, workspace_id: int
    ) -> Optional[ProductionFormulaItem]:
        """
        Get formula item by ID with workspace validation (SECURITY-CRITICAL)

        Args:
            db: Database session
            id: Formula item ID
            workspace_id: Workspace ID to filter by

        Returns:
            Formula item or None
        """
        return (
            db.query(ProductionFormulaItem)
            .filter(
                ProductionFormulaItem.id == id,
                ProductionFormulaItem.workspace_id == workspace_id
            )
            .first()
        )


production_formula_item_dao = ProductionFormulaItemDAO(ProductionFormulaItem)
