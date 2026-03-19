"""Production Batch DAO operations"""
from typing import List, Optional
from datetime import date, datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from app.dao.base import BaseDAO
from app.models.production_batch import ProductionBatch
from app.schemas.production_batch import ProductionBatchCreate, ProductionBatchUpdate


class ProductionBatchDAO(BaseDAO[ProductionBatch, ProductionBatchCreate, ProductionBatchUpdate]):
    """
    DAO operations for ProductionBatch model.
    All methods enforce workspace isolation for security.
    """

    def get_by_workspace(
        self, db: Session, *, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[ProductionBatch]:
        """
        Get all production batches for a workspace (SECURITY-CRITICAL)

        Args:
            db: Database session
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of production batches
        """
        return (
            db.query(ProductionBatch)
            .filter(ProductionBatch.workspace_id == workspace_id)
            .order_by(ProductionBatch.batch_date.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_batch_number(
        self, db: Session, *, batch_number: str, workspace_id: int
    ) -> Optional[ProductionBatch]:
        """
        Get batch by batch number (SECURITY-CRITICAL)

        Args:
            db: Database session
            batch_number: Batch number (e.g., "BATCH-2025-001")
            workspace_id: Workspace ID to filter by

        Returns:
            Production batch or None
        """
        return (
            db.query(ProductionBatch)
            .filter(
                ProductionBatch.workspace_id == workspace_id,
                ProductionBatch.batch_number == batch_number
            )
            .first()
        )

    def get_by_production_line(
        self, db: Session, *, production_line_id: int, workspace_id: int,
        skip: int = 0, limit: int = 100
    ) -> List[ProductionBatch]:
        """
        Get batches by production line (SECURITY-CRITICAL)

        Args:
            db: Database session
            production_line_id: Production line ID
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of production batches
        """
        return (
            db.query(ProductionBatch)
            .filter(
                ProductionBatch.workspace_id == workspace_id,
                ProductionBatch.production_line_id == production_line_id
            )
            .order_by(ProductionBatch.batch_date.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_formula(
        self, db: Session, *, formula_id: int, workspace_id: int,
        skip: int = 0, limit: int = 100
    ) -> List[ProductionBatch]:
        """
        Get batches by formula (SECURITY-CRITICAL)

        Args:
            db: Database session
            formula_id: Formula ID
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of production batches
        """
        return (
            db.query(ProductionBatch)
            .filter(
                ProductionBatch.workspace_id == workspace_id,
                ProductionBatch.formula_id == formula_id
            )
            .order_by(ProductionBatch.batch_date.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_status(
        self, db: Session, *, status: str, workspace_id: int,
        skip: int = 0, limit: int = 100
    ) -> List[ProductionBatch]:
        """
        Get batches by status (SECURITY-CRITICAL)

        Args:
            db: Database session
            status: Batch status ('draft', 'in_progress', 'completed', 'cancelled')
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of production batches
        """
        return (
            db.query(ProductionBatch)
            .filter(
                ProductionBatch.workspace_id == workspace_id,
                ProductionBatch.status == status
            )
            .order_by(ProductionBatch.batch_date.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_date_range(
        self, db: Session, *, start_date: date, end_date: date, workspace_id: int,
        skip: int = 0, limit: int = 100
    ) -> List[ProductionBatch]:
        """
        Get batches by date range (SECURITY-CRITICAL)

        Args:
            db: Database session
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of production batches
        """
        return (
            db.query(ProductionBatch)
            .filter(
                ProductionBatch.workspace_id == workspace_id,
                ProductionBatch.batch_date >= start_date,
                ProductionBatch.batch_date <= end_date
            )
            .order_by(ProductionBatch.batch_date.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_in_progress_batches(
        self, db: Session, *, workspace_id: int
    ) -> List[ProductionBatch]:
        """
        Get all in-progress batches (SECURITY-CRITICAL)

        Args:
            db: Database session
            workspace_id: Workspace ID to filter by

        Returns:
            List of in-progress production batches
        """
        return (
            db.query(ProductionBatch)
            .filter(
                ProductionBatch.workspace_id == workspace_id,
                ProductionBatch.status == 'in_progress'
            )
            .order_by(ProductionBatch.batch_date.desc())
            .all()
        )

    def get_completed_batches(
        self, db: Session, *, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> List[ProductionBatch]:
        """
        Get completed batches (SECURITY-CRITICAL)

        Args:
            db: Database session
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of completed production batches
        """
        return (
            db.query(ProductionBatch)
            .filter(
                ProductionBatch.workspace_id == workspace_id,
                ProductionBatch.status == 'completed'
            )
            .order_by(ProductionBatch.completed_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_id_and_workspace(
        self, db: Session, *, id: int, workspace_id: int
    ) -> Optional[ProductionBatch]:
        """
        Get batch by ID with workspace validation (SECURITY-CRITICAL)

        Args:
            db: Database session
            id: Batch ID
            workspace_id: Workspace ID to filter by

        Returns:
            Production batch or None
        """
        return (
            db.query(ProductionBatch)
            .filter(
                ProductionBatch.id == id,
                ProductionBatch.workspace_id == workspace_id
            )
            .first()
        )

    def generate_batch_number(
        self, db: Session, *, workspace_id: int, year: int = None
    ) -> str:
        """
        Generate next batch number for workspace

        Args:
            db: Database session
            workspace_id: Workspace ID
            year: Year for batch number (defaults to current year)

        Returns:
            Next batch number (e.g., "BATCH-2025-001")
        """
        if year is None:
            year = datetime.now().year

        # Find highest batch number for this workspace and year
        prefix = f"BATCH-{year}-"
        last_batch = (
            db.query(ProductionBatch)
            .filter(
                ProductionBatch.workspace_id == workspace_id,
                ProductionBatch.batch_number.like(f"{prefix}%")
            )
            .order_by(ProductionBatch.batch_number.desc())
            .first()
        )

        if last_batch:
            # Extract number and increment
            last_number = int(last_batch.batch_number.split('-')[-1])
            next_number = last_number + 1
        else:
            next_number = 1

        return f"{prefix}{next_number:03d}"


production_batch_dao = ProductionBatchDAO(ProductionBatch)
