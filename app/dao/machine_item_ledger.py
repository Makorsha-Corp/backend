"""Machine item ledger DAO operations"""
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from decimal import Decimal
from app.dao.base import BaseDAO
from app.models.machine_item_ledger import MachineItemLedger
from app.schemas.machine_item_ledger import MachineItemLedgerCreate, MachineItemLedgerUpdate


class MachineItemLedgerDAO(BaseDAO[MachineItemLedger, MachineItemLedgerCreate, MachineItemLedgerUpdate]):
    """DAO operations for MachineItemLedger model"""

    def get_by_machine_and_item(
        self, db: Session, *, machine_id: int, item_id: int, workspace_id: int,
        skip: int = 0, limit: int = 100
    ) -> List[MachineItemLedger]:
        """
        Get ledger entries for specific machine and item (SECURITY-CRITICAL)

        Args:
            db: Database session
            machine_id: Machine ID
            item_id: Item ID
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of ledger entries ordered by time (newest first)
        """
        return (
            db.query(MachineItemLedger)
            .filter(
                MachineItemLedger.workspace_id == workspace_id,
                MachineItemLedger.machine_id == machine_id,
                MachineItemLedger.item_id == item_id
            )
            .order_by(MachineItemLedger.performed_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_transaction_type(
        self, db: Session, *, transaction_type: str, workspace_id: int,
        skip: int = 0, limit: int = 100
    ) -> List[MachineItemLedger]:
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
            db.query(MachineItemLedger)
            .filter(
                MachineItemLedger.workspace_id == workspace_id,
                MachineItemLedger.transaction_type == transaction_type
            )
            .order_by(MachineItemLedger.performed_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_order(
        self, db: Session, *, order_id: int, workspace_id: int
    ) -> List[MachineItemLedger]:
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
            db.query(MachineItemLedger)
            .filter(
                MachineItemLedger.workspace_id == workspace_id,
                MachineItemLedger.order_id == order_id
            )
            .order_by(MachineItemLedger.performed_at)
            .all()
        )

    def get_by_date_range(
        self, db: Session, *, workspace_id: int, start_date: datetime, end_date: datetime,
        skip: int = 0, limit: int = 100
    ) -> List[MachineItemLedger]:
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
            db.query(MachineItemLedger)
            .filter(
                MachineItemLedger.workspace_id == workspace_id,
                MachineItemLedger.performed_at >= start_date,
                MachineItemLedger.performed_at <= end_date
            )
            .order_by(MachineItemLedger.performed_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_machine(
        self, db: Session, *, machine_id: int, workspace_id: int,
        skip: int = 0, limit: int = 100
    ) -> List[MachineItemLedger]:
        """
        Get all ledger entries for a machine (SECURITY-CRITICAL)

        Args:
            db: Database session
            machine_id: Machine ID
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of ledger entries for the machine
        """
        return (
            db.query(MachineItemLedger)
            .filter(
                MachineItemLedger.workspace_id == workspace_id,
                MachineItemLedger.machine_id == machine_id
            )
            .order_by(MachineItemLedger.performed_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_consumption_entries(
        self, db: Session, *, machine_id: int, workspace_id: int,
        start_date: datetime = None, end_date: datetime = None
    ) -> List[MachineItemLedger]:
        """
        Get consumption entries for a machine (SECURITY-CRITICAL)

        Args:
            db: Database session
            machine_id: Machine ID
            workspace_id: Workspace ID to filter by
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            List of consumption ledger entries
        """
        query = db.query(MachineItemLedger).filter(
            MachineItemLedger.workspace_id == workspace_id,
            MachineItemLedger.machine_id == machine_id,
            MachineItemLedger.transaction_type == 'consumption'
        )

        if start_date:
            query = query.filter(MachineItemLedger.performed_at >= start_date)
        if end_date:
            query = query.filter(MachineItemLedger.performed_at <= end_date)

        return query.order_by(MachineItemLedger.performed_at.desc()).all()

    def calculate_balance(
        self, db: Session, *, machine_id: int, item_id: int, workspace_id: int
    ) -> tuple[int, Decimal]:
        """
        Calculate current balance from ledger (for reconciliation)

        Args:
            db: Database session
            machine_id: Machine ID
            item_id: Item ID
            workspace_id: Workspace ID to filter by

        Returns:
            Tuple of (quantity, total_value)
        """
        entry = (
            db.query(MachineItemLedger)
            .filter(
                MachineItemLedger.workspace_id == workspace_id,
                MachineItemLedger.machine_id == machine_id,
                MachineItemLedger.item_id == item_id
            )
            .order_by(MachineItemLedger.performed_at.desc())
            .first()
        )

        if entry:
            return (entry.qty_after, entry.value_after or Decimal('0.00'))
        return (0, Decimal('0.00'))

    def get_latest_entry(
        self, db: Session, *, machine_id: int, item_id: int, workspace_id: int
    ) -> Optional[MachineItemLedger]:
        """
        Get the most recent ledger entry for machine/item (SECURITY-CRITICAL)

        Args:
            db: Database session
            machine_id: Machine ID
            item_id: Item ID
            workspace_id: Workspace ID to filter by

        Returns:
            Latest ledger entry or None
        """
        return (
            db.query(MachineItemLedger)
            .filter(
                MachineItemLedger.workspace_id == workspace_id,
                MachineItemLedger.machine_id == machine_id,
                MachineItemLedger.item_id == item_id
            )
            .order_by(MachineItemLedger.performed_at.desc())
            .first()
        )


machine_item_ledger_dao = MachineItemLedgerDAO(MachineItemLedger)
