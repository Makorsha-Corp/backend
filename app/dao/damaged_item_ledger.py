"""Damaged item ledger DAO operations"""
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from decimal import Decimal
from app.dao.base import BaseDAO
from app.models.damaged_item_ledger import DamagedItemLedger
from app.schemas.damaged_item_ledger import DamagedItemLedgerCreate, DamagedItemLedgerUpdate


class DamagedItemLedgerDAO(BaseDAO[DamagedItemLedger, DamagedItemLedgerCreate, DamagedItemLedgerUpdate]):
    """DAO operations for DamagedItemLedger model"""

    def get_by_factory_and_item(
        self, db: Session, *, factory_id: int, item_id: int, workspace_id: int,
        skip: int = 0, limit: int = 100
    ) -> List[DamagedItemLedger]:
        """
        Get ledger entries for specific factory and item (SECURITY-CRITICAL)

        Args:
            db: Database session
            factory_id: Factory ID
            item_id: Item ID
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of ledger entries ordered by time (newest first)
        """
        return (
            db.query(DamagedItemLedger)
            .filter(
                DamagedItemLedger.workspace_id == workspace_id,
                DamagedItemLedger.factory_id == factory_id,
                DamagedItemLedger.item_id == item_id
            )
            .order_by(DamagedItemLedger.performed_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_transaction_type(
        self, db: Session, *, transaction_type: str, workspace_id: int,
        skip: int = 0, limit: int = 100
    ) -> List[DamagedItemLedger]:
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
            db.query(DamagedItemLedger)
            .filter(
                DamagedItemLedger.workspace_id == workspace_id,
                DamagedItemLedger.transaction_type == transaction_type
            )
            .order_by(DamagedItemLedger.performed_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_order(
        self, db: Session, *, order_id: int, workspace_id: int
    ) -> List[DamagedItemLedger]:
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
            db.query(DamagedItemLedger)
            .filter(
                DamagedItemLedger.workspace_id == workspace_id,
                DamagedItemLedger.order_id == order_id
            )
            .order_by(DamagedItemLedger.performed_at)
            .all()
        )

    def get_by_date_range(
        self, db: Session, *, workspace_id: int, start_date: datetime, end_date: datetime,
        skip: int = 0, limit: int = 100
    ) -> List[DamagedItemLedger]:
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
            db.query(DamagedItemLedger)
            .filter(
                DamagedItemLedger.workspace_id == workspace_id,
                DamagedItemLedger.performed_at >= start_date,
                DamagedItemLedger.performed_at <= end_date
            )
            .order_by(DamagedItemLedger.performed_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_damage_reports(
        self, db: Session, *, workspace_id: int, factory_id: int = None,
        start_date: datetime = None, end_date: datetime = None
    ) -> List[DamagedItemLedger]:
        """
        Get damage report entries (items marked as damaged)

        Args:
            db: Database session
            workspace_id: Workspace ID to filter by
            factory_id: Optional factory filter
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            List of damage report ledger entries
        """
        query = db.query(DamagedItemLedger).filter(
            DamagedItemLedger.workspace_id == workspace_id,
            DamagedItemLedger.transaction_type == 'damaged'
        )

        if factory_id:
            query = query.filter(DamagedItemLedger.factory_id == factory_id)
        if start_date:
            query = query.filter(DamagedItemLedger.performed_at >= start_date)
        if end_date:
            query = query.filter(DamagedItemLedger.performed_at <= end_date)

        return query.order_by(DamagedItemLedger.performed_at.desc()).all()

    def calculate_balance(
        self, db: Session, *, factory_id: int, item_id: int, workspace_id: int
    ) -> tuple[int, Decimal]:
        """
        Calculate current balance from ledger (for reconciliation)

        Args:
            db: Database session
            factory_id: Factory ID
            item_id: Item ID
            workspace_id: Workspace ID to filter by

        Returns:
            Tuple of (quantity, total_value)
        """
        entry = (
            db.query(DamagedItemLedger)
            .filter(
                DamagedItemLedger.workspace_id == workspace_id,
                DamagedItemLedger.factory_id == factory_id,
                DamagedItemLedger.item_id == item_id
            )
            .order_by(DamagedItemLedger.performed_at.desc())
            .first()
        )

        if entry:
            return (entry.qty_after, entry.value_after or Decimal('0.00'))
        return (0, Decimal('0.00'))

    def get_latest_entry(
        self, db: Session, *, factory_id: int, item_id: int, workspace_id: int
    ) -> Optional[DamagedItemLedger]:
        """
        Get the most recent ledger entry for factory/item (SECURITY-CRITICAL)

        Args:
            db: Database session
            factory_id: Factory ID
            item_id: Item ID
            workspace_id: Workspace ID to filter by

        Returns:
            Latest ledger entry or None
        """
        return (
            db.query(DamagedItemLedger)
            .filter(
                DamagedItemLedger.workspace_id == workspace_id,
                DamagedItemLedger.factory_id == factory_id,
                DamagedItemLedger.item_id == item_id
            )
            .order_by(DamagedItemLedger.performed_at.desc())
            .first()
        )


damaged_item_ledger_dao = DamagedItemLedgerDAO(DamagedItemLedger)
