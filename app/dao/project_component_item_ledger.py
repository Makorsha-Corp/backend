"""Project component item ledger DAO operations"""
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from decimal import Decimal
from app.dao.base import BaseDAO
from app.models.project_component_item_ledger import ProjectComponentItemLedger
from app.schemas.project_component_item_ledger import ProjectComponentItemLedgerCreate, ProjectComponentItemLedgerUpdate


class ProjectComponentItemLedgerDAO(BaseDAO[ProjectComponentItemLedger, ProjectComponentItemLedgerCreate, ProjectComponentItemLedgerUpdate]):
    """DAO operations for ProjectComponentItemLedger model"""

    def get_by_component_and_item(
        self, db: Session, *, project_component_id: int, item_id: int, workspace_id: int,
        skip: int = 0, limit: int = 100
    ) -> List[ProjectComponentItemLedger]:
        """
        Get ledger entries for specific component and item (SECURITY-CRITICAL)

        Args:
            db: Database session
            project_component_id: Project component ID
            item_id: Item ID
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of ledger entries ordered by time (newest first)
        """
        return (
            db.query(ProjectComponentItemLedger)
            .filter(
                ProjectComponentItemLedger.workspace_id == workspace_id,
                ProjectComponentItemLedger.project_component_id == project_component_id,
                ProjectComponentItemLedger.item_id == item_id
            )
            .order_by(ProjectComponentItemLedger.performed_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_component(
        self, db: Session, *, project_component_id: int, workspace_id: int,
        skip: int = 0, limit: int = 100
    ) -> List[ProjectComponentItemLedger]:
        """
        Get all ledger entries for a component (SECURITY-CRITICAL)

        Args:
            db: Database session
            project_component_id: Project component ID
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of ledger entries for the component
        """
        return (
            db.query(ProjectComponentItemLedger)
            .filter(
                ProjectComponentItemLedger.workspace_id == workspace_id,
                ProjectComponentItemLedger.project_component_id == project_component_id
            )
            .order_by(ProjectComponentItemLedger.performed_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_transaction_type(
        self, db: Session, *, transaction_type: str, workspace_id: int,
        skip: int = 0, limit: int = 100
    ) -> List[ProjectComponentItemLedger]:
        """
        Get ledger entries by transaction type (SECURITY-CRITICAL)

        Args:
            db: Database session
            transaction_type: Transaction type to filter by
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of ledger entries
        """
        return (
            db.query(ProjectComponentItemLedger)
            .filter(
                ProjectComponentItemLedger.workspace_id == workspace_id,
                ProjectComponentItemLedger.transaction_type == transaction_type
            )
            .order_by(ProjectComponentItemLedger.performed_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_order(
        self, db: Session, *, order_id: int, workspace_id: int
    ) -> List[ProjectComponentItemLedger]:
        """
        Get all ledger entries for an order (SECURITY-CRITICAL)

        Args:
            db: Database session
            order_id: Order ID
            workspace_id: Workspace ID to filter by

        Returns:
            List of ledger entries for the order
        """
        return (
            db.query(ProjectComponentItemLedger)
            .filter(
                ProjectComponentItemLedger.workspace_id == workspace_id,
                ProjectComponentItemLedger.order_id == order_id
            )
            .order_by(ProjectComponentItemLedger.performed_at)
            .all()
        )

    def get_by_date_range(
        self, db: Session, *, workspace_id: int, start_date: datetime, end_date: datetime,
        skip: int = 0, limit: int = 100
    ) -> List[ProjectComponentItemLedger]:
        """
        Get ledger entries within date range (SECURITY-CRITICAL)

        Args:
            db: Database session
            workspace_id: Workspace ID to filter by
            start_date: Start datetime (inclusive)
            end_date: End datetime (inclusive)
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of ledger entries in date range
        """
        return (
            db.query(ProjectComponentItemLedger)
            .filter(
                ProjectComponentItemLedger.workspace_id == workspace_id,
                ProjectComponentItemLedger.performed_at >= start_date,
                ProjectComponentItemLedger.performed_at <= end_date
            )
            .order_by(ProjectComponentItemLedger.performed_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_consumption_entries(
        self, db: Session, *, project_component_id: int, workspace_id: int,
        start_date: datetime = None, end_date: datetime = None
    ) -> List[ProjectComponentItemLedger]:
        """
        Get consumption entries for a project component (SECURITY-CRITICAL)

        Args:
            db: Database session
            project_component_id: Project component ID
            workspace_id: Workspace ID to filter by
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            List of consumption ledger entries
        """
        query = db.query(ProjectComponentItemLedger).filter(
            ProjectComponentItemLedger.workspace_id == workspace_id,
            ProjectComponentItemLedger.project_component_id == project_component_id,
            ProjectComponentItemLedger.transaction_type == 'consumption'
        )

        if start_date:
            query = query.filter(ProjectComponentItemLedger.performed_at >= start_date)
        if end_date:
            query = query.filter(ProjectComponentItemLedger.performed_at <= end_date)

        return query.order_by(ProjectComponentItemLedger.performed_at.desc()).all()

    def calculate_balance(
        self, db: Session, *, project_component_id: int, item_id: int, workspace_id: int
    ) -> tuple[int, Decimal]:
        """
        Calculate current balance from ledger (for reconciliation)

        Args:
            db: Database session
            project_component_id: Project component ID
            item_id: Item ID
            workspace_id: Workspace ID to filter by

        Returns:
            Tuple of (quantity, total_value)
        """
        entry = (
            db.query(ProjectComponentItemLedger)
            .filter(
                ProjectComponentItemLedger.workspace_id == workspace_id,
                ProjectComponentItemLedger.project_component_id == project_component_id,
                ProjectComponentItemLedger.item_id == item_id
            )
            .order_by(ProjectComponentItemLedger.performed_at.desc())
            .first()
        )

        if entry:
            return (entry.qty_after, entry.value_after or Decimal('0.00'))
        return (0, Decimal('0.00'))

    def get_latest_entry(
        self, db: Session, *, project_component_id: int, item_id: int, workspace_id: int
    ) -> Optional[ProjectComponentItemLedger]:
        """
        Get the most recent ledger entry for component/item (SECURITY-CRITICAL)

        Args:
            db: Database session
            project_component_id: Project component ID
            item_id: Item ID
            workspace_id: Workspace ID to filter by

        Returns:
            Latest ledger entry or None
        """
        return (
            db.query(ProjectComponentItemLedger)
            .filter(
                ProjectComponentItemLedger.workspace_id == workspace_id,
                ProjectComponentItemLedger.project_component_id == project_component_id,
                ProjectComponentItemLedger.item_id == item_id
            )
            .order_by(ProjectComponentItemLedger.performed_at.desc())
            .first()
        )

    def calculate_total_cost_for_component(
        self, db: Session, *, project_component_id: int, workspace_id: int
    ) -> Decimal:
        """
        Calculate total cost of all items allocated to component

        Args:
            db: Database session
            project_component_id: Project component ID
            workspace_id: Workspace ID to filter by

        Returns:
            Total cost
        """
        from sqlalchemy import func

        result = (
            db.query(func.sum(ProjectComponentItemLedger.total_cost))
            .filter(
                ProjectComponentItemLedger.workspace_id == workspace_id,
                ProjectComponentItemLedger.project_component_id == project_component_id
            )
            .scalar()
        )

        return result if result else Decimal('0.00')


project_component_item_ledger_dao = ProjectComponentItemLedgerDAO(ProjectComponentItemLedger)
