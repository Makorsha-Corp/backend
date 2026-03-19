"""Production Line DAO operations"""
from typing import List, Optional
from sqlalchemy.orm import Session
from app.dao.base import BaseDAO
from app.models.production_line import ProductionLine
from app.schemas.production_line import ProductionLineCreate, ProductionLineUpdate


class ProductionLineDAO(BaseDAO[ProductionLine, ProductionLineCreate, ProductionLineUpdate]):
    """
    DAO operations for ProductionLine model.
    All methods enforce workspace isolation for security.
    """

    def get_by_workspace(
        self, db: Session, *, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[ProductionLine]:
        """
        Get all production lines for a workspace (SECURITY-CRITICAL)

        Args:
            db: Database session
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of production lines
        """
        return (
            db.query(ProductionLine)
            .filter(ProductionLine.workspace_id == workspace_id)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_factory(
        self, db: Session, *, factory_id: int, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[ProductionLine]:
        """
        Get production lines by factory (SECURITY-CRITICAL)

        Args:
            db: Database session
            factory_id: Factory ID
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of production lines at the factory
        """
        return (
            db.query(ProductionLine)
            .filter(
                ProductionLine.workspace_id == workspace_id,
                ProductionLine.factory_id == factory_id
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_machine(
        self, db: Session, *, machine_id: int, workspace_id: int
    ) -> List[ProductionLine]:
        """
        Get production lines attached to a machine (SECURITY-CRITICAL)

        Args:
            db: Database session
            machine_id: Machine ID
            workspace_id: Workspace ID to filter by

        Returns:
            List of production lines attached to machine
        """
        return (
            db.query(ProductionLine)
            .filter(
                ProductionLine.workspace_id == workspace_id,
                ProductionLine.machine_id == machine_id
            )
            .all()
        )

    def get_active_by_workspace(
        self, db: Session, *, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[ProductionLine]:
        """
        Get active production lines for a workspace (SECURITY-CRITICAL)

        Args:
            db: Database session
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of active production lines
        """
        return (
            db.query(ProductionLine)
            .filter(
                ProductionLine.workspace_id == workspace_id,
                ProductionLine.is_active == True
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_standalone_lines(
        self, db: Session, *, workspace_id: int
    ) -> List[ProductionLine]:
        """
        Get standalone production lines (not attached to machines) (SECURITY-CRITICAL)

        Args:
            db: Database session
            workspace_id: Workspace ID to filter by

        Returns:
            List of standalone production lines
        """
        return (
            db.query(ProductionLine)
            .filter(
                ProductionLine.workspace_id == workspace_id,
                ProductionLine.machine_id.is_(None)
            )
            .all()
        )

    def get_by_id_and_workspace(
        self, db: Session, *, id: int, workspace_id: int
    ) -> Optional[ProductionLine]:
        """
        Get production line by ID with workspace validation (SECURITY-CRITICAL)

        Args:
            db: Database session
            id: Production line ID
            workspace_id: Workspace ID to filter by

        Returns:
            Production line or None
        """
        return (
            db.query(ProductionLine)
            .filter(
                ProductionLine.id == id,
                ProductionLine.workspace_id == workspace_id
            )
            .first()
        )


production_line_dao = ProductionLineDAO(ProductionLine)
