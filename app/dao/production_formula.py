"""Production Formula DAO operations"""
from typing import List, Optional
from sqlalchemy.orm import Session
from app.dao.base import BaseDAO
from app.models.production_formula import ProductionFormula
from app.schemas.production_formula import ProductionFormulaCreate, ProductionFormulaUpdate


class ProductionFormulaDAO(BaseDAO[ProductionFormula, ProductionFormulaCreate, ProductionFormulaUpdate]):
    """
    DAO operations for ProductionFormula model.
    All methods enforce workspace isolation for security.
    """

    def get_by_workspace(
        self, db: Session, *, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[ProductionFormula]:
        """
        Get all production formulas for a workspace (SECURITY-CRITICAL)

        Args:
            db: Database session
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of production formulas
        """
        return (
            db.query(ProductionFormula)
            .filter(ProductionFormula.workspace_id == workspace_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_formula_code(
        self, db: Session, *, formula_code: str, workspace_id: int
    ) -> Optional[ProductionFormula]:
        """
        Get production formula by formula code (SECURITY-CRITICAL)

        Args:
            db: Database session
            formula_code: Formula code (e.g., "YARN-001")
            workspace_id: Workspace ID to filter by

        Returns:
            Production formula or None
        """
        return (
            db.query(ProductionFormula)
            .filter(
                ProductionFormula.workspace_id == workspace_id,
                ProductionFormula.formula_code == formula_code
            )
            .first()
        )

    def get_active_by_workspace(
        self, db: Session, *, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[ProductionFormula]:
        """
        Get active production formulas for a workspace (SECURITY-CRITICAL)

        Args:
            db: Database session
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of active production formulas
        """
        return (
            db.query(ProductionFormula)
            .filter(
                ProductionFormula.workspace_id == workspace_id,
                ProductionFormula.is_active == True
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_default_formulas(
        self, db: Session, *, workspace_id: int
    ) -> List[ProductionFormula]:
        """
        Get all default formulas in a workspace (SECURITY-CRITICAL)

        Args:
            db: Database session
            workspace_id: Workspace ID to filter by

        Returns:
            List of default production formulas
        """
        return (
            db.query(ProductionFormula)
            .filter(
                ProductionFormula.workspace_id == workspace_id,
                ProductionFormula.is_default == True,
                ProductionFormula.is_active == True
            )
            .all()
        )

    def get_by_id_and_workspace(
        self, db: Session, *, id: int, workspace_id: int
    ) -> Optional[ProductionFormula]:
        """
        Get production formula by ID with workspace validation (SECURITY-CRITICAL)

        Args:
            db: Database session
            id: Production formula ID
            workspace_id: Workspace ID to filter by

        Returns:
            Production formula or None
        """
        return (
            db.query(ProductionFormula)
            .filter(
                ProductionFormula.id == id,
                ProductionFormula.workspace_id == workspace_id
            )
            .first()
        )

    def get_formula_versions(
        self, db: Session, *, formula_code: str, workspace_id: int
    ) -> List[ProductionFormula]:
        """
        Get all versions of a formula (SECURITY-CRITICAL)

        Args:
            db: Database session
            formula_code: Formula code
            workspace_id: Workspace ID to filter by

        Returns:
            List of formula versions ordered by version number
        """
        return (
            db.query(ProductionFormula)
            .filter(
                ProductionFormula.workspace_id == workspace_id,
                ProductionFormula.formula_code == formula_code
            )
            .order_by(ProductionFormula.version.desc())
            .all()
        )


production_formula_dao = ProductionFormulaDAO(ProductionFormula)
