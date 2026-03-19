"""Storage item ledger DAO operations"""
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List, Optional
from datetime import datetime, date
from decimal import Decimal
from app.dao.base import BaseDAO
from app.models.storage_item_ledger import StorageItemLedger
from app.schemas.storage_item_ledger import StorageItemLedgerCreate, StorageItemLedgerUpdate


class StorageItemLedgerDAO(BaseDAO[StorageItemLedger, StorageItemLedgerCreate, StorageItemLedgerUpdate]):
    """DAO operations for StorageItemLedger model"""

    def get_by_factory_and_item(
        self, db: Session, *, factory_id: int, item_id: int, workspace_id: int,
        skip: int = 0, limit: int = 100
    ) -> List[StorageItemLedger]:
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
            db.query(StorageItemLedger)
            .filter(
                StorageItemLedger.workspace_id == workspace_id,
                StorageItemLedger.factory_id == factory_id,
                StorageItemLedger.item_id == item_id
            )
            .order_by(StorageItemLedger.performed_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_transaction_type(
        self, db: Session, *, transaction_type: str, workspace_id: int,
        skip: int = 0, limit: int = 100
    ) -> List[StorageItemLedger]:
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
            db.query(StorageItemLedger)
            .filter(
                StorageItemLedger.workspace_id == workspace_id,
                StorageItemLedger.transaction_type == transaction_type
            )
            .order_by(StorageItemLedger.performed_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_order(
        self, db: Session, *, order_id: int, workspace_id: int
    ) -> List[StorageItemLedger]:
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
            db.query(StorageItemLedger)
            .filter(
                StorageItemLedger.workspace_id == workspace_id,
                StorageItemLedger.order_id == order_id
            )
            .order_by(StorageItemLedger.performed_at)
            .all()
        )

    def get_by_date_range(
        self, db: Session, *, workspace_id: int, start_date: datetime, end_date: datetime,
        skip: int = 0, limit: int = 100
    ) -> List[StorageItemLedger]:
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
            db.query(StorageItemLedger)
            .filter(
                StorageItemLedger.workspace_id == workspace_id,
                StorageItemLedger.performed_at >= start_date,
                StorageItemLedger.performed_at <= end_date
            )
            .order_by(StorageItemLedger.performed_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_performer(
        self, db: Session, *, performed_by: int, workspace_id: int,
        skip: int = 0, limit: int = 100
    ) -> List[StorageItemLedger]:
        """
        Get ledger entries by performer (SECURITY-CRITICAL)

        Args:
            db: Database session
            performed_by: User ID who performed transactions
            workspace_id: Workspace ID to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of ledger entries
        """
        return (
            db.query(StorageItemLedger)
            .filter(
                StorageItemLedger.workspace_id == workspace_id,
                StorageItemLedger.performed_by == performed_by
            )
            .order_by(StorageItemLedger.performed_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

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
        entries = (
            db.query(StorageItemLedger)
            .filter(
                StorageItemLedger.workspace_id == workspace_id,
                StorageItemLedger.factory_id == factory_id,
                StorageItemLedger.item_id == item_id
            )
            .order_by(StorageItemLedger.performed_at.desc())
            .first()
        )

        if entries:
            return (entries.qty_after, entries.value_after or Decimal('0.00'))
        return (0, Decimal('0.00'))

    def get_latest_entry(
        self, db: Session, *, factory_id: int, item_id: int, workspace_id: int
    ) -> Optional[StorageItemLedger]:
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
            db.query(StorageItemLedger)
            .filter(
                StorageItemLedger.workspace_id == workspace_id,
                StorageItemLedger.factory_id == factory_id,
                StorageItemLedger.item_id == item_id
            )
            .order_by(StorageItemLedger.performed_at.desc())
            .first()
        )


storage_item_ledger_dao = StorageItemLedgerDAO(StorageItemLedger)
