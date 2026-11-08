"""Production Batch DAO operations"""
import re
from typing import List, Optional
from datetime import date, datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from app.models.production_line import ProductionLine
from app.dao.base import BaseDAO
from app.models.production_batch import ProductionBatch
from app.schemas.production_batch import ProductionBatchCreate, ProductionBatchUpdate


class ProductionBatchDAO(BaseDAO[ProductionBatch, ProductionBatchCreate, ProductionBatchUpdate]):
    """
    DAO operations for ProductionBatch model.
    All methods enforce workspace isolation for security.
    """

    def get_by_factory(
        self,
        db: Session,
        *,
        workspace_id: int,
        factory_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> List[ProductionBatch]:
        """Batches whose production line belongs to the factory."""
        return (
            db.query(ProductionBatch)
            .join(ProductionLine, ProductionBatch.production_line_id == ProductionLine.id)
            .filter(
                ProductionBatch.workspace_id == workspace_id,
                ProductionLine.factory_id == factory_id,
            )
            .order_by(ProductionBatch.batch_date.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

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
            batch_number: Batch number (e.g., "B-2025-001")
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

    def count_by_status(
        self,
        db: Session,
        *,
        workspace_id: int,
        status: str,
        factory_id: Optional[int] = None,
    ) -> int:
        query = db.query(func.count(ProductionBatch.id)).filter(
            ProductionBatch.workspace_id == workspace_id,
            ProductionBatch.status == status,
        )
        if factory_id is not None:
            query = query.join(
                ProductionLine, ProductionBatch.production_line_id == ProductionLine.id
            ).filter(ProductionLine.factory_id == factory_id)
        return query.scalar() or 0

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

    def get_by_program(
        self, db: Session, *, program_id: int, workspace_id: int
    ) -> List[ProductionBatch]:
        """Batches linked to one program in this workspace."""
        return (
            db.query(ProductionBatch)
            .filter(
                ProductionBatch.workspace_id == workspace_id,
                ProductionBatch.program_id == program_id,
            )
            .order_by(ProductionBatch.id.asc())
            .all()
        )

    def get_by_program_ids(
        self, db: Session, *, program_ids: List[int], workspace_id: int
    ) -> List[ProductionBatch]:
        """Batches for several programs in this workspace, earliest planned start first."""
        if not program_ids:
            return []
        return (
            db.query(ProductionBatch)
            .filter(
                ProductionBatch.workspace_id == workspace_id,
                ProductionBatch.program_id.in_(program_ids),
            )
            .order_by(ProductionBatch.planned_start_at.asc(), ProductionBatch.id.asc())
            .all()
        )

    def count_by_program_ids(
        self, db: Session, *, program_ids: List[int], workspace_id: int
    ) -> dict[int, int]:
        """Batch counts for programs in this workspace. Missing ids count as absent."""
        if not program_ids:
            return {}
        rows = (
            db.query(ProductionBatch.program_id, func.count(ProductionBatch.id))
            .filter(
                ProductionBatch.workspace_id == workspace_id,
                ProductionBatch.program_id.in_(program_ids),
            )
            .group_by(ProductionBatch.program_id)
            .all()
        )
        return {int(program_id): int(count) for program_id, count in rows}

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

    @staticmethod
    def sequence_from_batch_number(batch_number: str, year: int) -> Optional[int]:
        """Parse sequence from ``B-{year}-{seq}``, legacy ``BATCH-{year}-{seq}``, or ``{year}-{seq}``."""
        y = str(year)
        normalized = batch_number.strip()
        for pattern in (
            rf"^B-{re.escape(y)}-(\d+)$",
            rf"^BATCH-{re.escape(y)}-(\d+)$",
            rf"^{re.escape(y)}-(\d+)$",
        ):
            match = re.match(pattern, normalized, re.IGNORECASE if "BATCH" in pattern else 0)
            if match:
                return int(match.group(1))
        return None

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
            Next batch number (e.g., "B-2025-001")
        """
        if year is None:
            year = datetime.now().year

        rows = (
            db.query(ProductionBatch.batch_number)
            .filter(
                ProductionBatch.workspace_id == workspace_id,
                or_(
                    ProductionBatch.batch_number.like(f"B-{year}-%"),
                    ProductionBatch.batch_number.like(f"BATCH-{year}-%"),
                    ProductionBatch.batch_number.like(f"{year}-%"),
                ),
            )
            .all()
        )

        max_seq = 0
        for (batch_number,) in rows:
            seq = self.sequence_from_batch_number(batch_number, year)
            if seq is not None:
                max_seq = max(max_seq, seq)

        return f"B-{year}-{max_seq + 1:03d}"


production_batch_dao = ProductionBatchDAO(ProductionBatch)
