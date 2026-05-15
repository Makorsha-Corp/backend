"""Unified inventory ledger DAO

SECURITY: All queries MUST filter by workspace_id.

The unified inventory_ledger table holds transactions for ALL inventory types
(STORAGE, DAMAGED, WASTE, SCRAP). Methods that compute per-bucket state
(`calculate_balance`, `get_latest_entry`) require `inventory_type` because each
(factory_id, item_id, inventory_type) tuple is an independent balance bucket.
"""
from typing import List, Optional
from datetime import datetime
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.dao.base import BaseDAO
from app.models.inventory_ledger import InventoryLedger
from app.models.enums import InventoryTypeEnum
from app.schemas.inventory_ledger import InventoryLedgerCreate, InventoryLedgerUpdate


class InventoryLedgerDAO(BaseDAO[InventoryLedger, InventoryLedgerCreate, InventoryLedgerUpdate]):
    """DAO for unified InventoryLedger model (workspace-scoped)"""

    def get_by_workspace(
        self, db: Session, *, workspace_id: int,
        inventory_type: Optional[InventoryTypeEnum] = None,
        factory_id: Optional[int] = None,
        item_id: Optional[int] = None,
        skip: int = 0, limit: int = 100
    ) -> List[InventoryLedger]:
        """Get ledger entries with optional filters, newest first."""
        query = db.query(InventoryLedger).filter(
            InventoryLedger.workspace_id == workspace_id,
        )
        if inventory_type:
            query = query.filter(InventoryLedger.inventory_type == inventory_type)
        if factory_id:
            query = query.filter(InventoryLedger.factory_id == factory_id)
        if item_id:
            query = query.filter(InventoryLedger.item_id == item_id)
        return query.order_by(desc(InventoryLedger.performed_at)).offset(skip).limit(limit).all()

    def get_by_id_and_workspace(
        self, db: Session, *, id: int, workspace_id: int
    ) -> Optional[InventoryLedger]:
        """Get ledger entry by ID with workspace isolation."""
        return db.query(InventoryLedger).filter(
            InventoryLedger.id == id,
            InventoryLedger.workspace_id == workspace_id,
        ).first()

    def get_by_factory_and_item(
        self, db: Session, *, factory_id: int, item_id: int, workspace_id: int,
        inventory_type: Optional[InventoryTypeEnum] = None,
        skip: int = 0, limit: int = 100
    ) -> List[InventoryLedger]:
        """Get ledger entries for a specific factory/item; optionally narrow to one inventory_type."""
        query = db.query(InventoryLedger).filter(
            InventoryLedger.workspace_id == workspace_id,
            InventoryLedger.factory_id == factory_id,
            InventoryLedger.item_id == item_id,
        )
        if inventory_type:
            query = query.filter(InventoryLedger.inventory_type == inventory_type)
        return (
            query.order_by(desc(InventoryLedger.performed_at))
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_transaction_type(
        self, db: Session, *, transaction_type: str, workspace_id: int,
        inventory_type: Optional[InventoryTypeEnum] = None,
        factory_id: Optional[int] = None,
        item_id: Optional[int] = None,
        skip: int = 0, limit: int = 100
    ) -> List[InventoryLedger]:
        """Get ledger entries by transaction type, with optional filters."""
        query = db.query(InventoryLedger).filter(
            InventoryLedger.workspace_id == workspace_id,
            InventoryLedger.transaction_type == transaction_type,
        )
        if inventory_type:
            query = query.filter(InventoryLedger.inventory_type == inventory_type)
        if factory_id:
            query = query.filter(InventoryLedger.factory_id == factory_id)
        if item_id:
            query = query.filter(InventoryLedger.item_id == item_id)
        return (
            query.order_by(desc(InventoryLedger.performed_at))
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_date_range(
        self, db: Session, *, workspace_id: int,
        start_date: datetime, end_date: datetime,
        inventory_type: Optional[InventoryTypeEnum] = None,
        factory_id: Optional[int] = None,
        item_id: Optional[int] = None,
        skip: int = 0, limit: int = 100
    ) -> List[InventoryLedger]:
        """Get ledger entries within date range, with optional filters."""
        query = db.query(InventoryLedger).filter(
            InventoryLedger.workspace_id == workspace_id,
            InventoryLedger.performed_at >= start_date,
            InventoryLedger.performed_at <= end_date,
        )
        if inventory_type:
            query = query.filter(InventoryLedger.inventory_type == inventory_type)
        if factory_id:
            query = query.filter(InventoryLedger.factory_id == factory_id)
        if item_id:
            query = query.filter(InventoryLedger.item_id == item_id)
        return (
            query.order_by(desc(InventoryLedger.performed_at))
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_order(
        self, db: Session, *, order_id: int, workspace_id: int
    ) -> List[InventoryLedger]:
        """Get all ledger entries linked to a specific order."""
        return (
            db.query(InventoryLedger)
            .filter(
                InventoryLedger.workspace_id == workspace_id,
                InventoryLedger.order_id == order_id,
            )
            .order_by(InventoryLedger.performed_at)
            .all()
        )

    def get_by_performer(
        self, db: Session, *, performed_by: int, workspace_id: int,
        skip: int = 0, limit: int = 100
    ) -> List[InventoryLedger]:
        """Get ledger entries performed by a specific user."""
        return (
            db.query(InventoryLedger)
            .filter(
                InventoryLedger.workspace_id == workspace_id,
                InventoryLedger.performed_by == performed_by,
            )
            .order_by(desc(InventoryLedger.performed_at))
            .offset(skip)
            .limit(limit)
            .all()
        )

    def calculate_balance(
        self, db: Session, *, factory_id: int, item_id: int,
        inventory_type: InventoryTypeEnum, workspace_id: int
    ) -> tuple[int, Decimal]:
        """Return (qty, total_value) for one (factory, item, inventory_type) bucket.

        Each inventory_type is an independent bucket and must be specified.
        Returns (0, 0.00) when no entries exist yet.
        """
        entry = (
            db.query(InventoryLedger)
            .filter(
                InventoryLedger.workspace_id == workspace_id,
                InventoryLedger.factory_id == factory_id,
                InventoryLedger.item_id == item_id,
                InventoryLedger.inventory_type == inventory_type,
            )
            .order_by(desc(InventoryLedger.performed_at))
            .first()
        )
        if entry:
            return (entry.qty_after, entry.value_after or Decimal('0.00'))
        return (0, Decimal('0.00'))

    def get_latest_entry(
        self, db: Session, *, factory_id: int, item_id: int,
        inventory_type: InventoryTypeEnum, workspace_id: int
    ) -> Optional[InventoryLedger]:
        """Get the most recent ledger entry for one (factory, item, inventory_type) bucket."""
        return (
            db.query(InventoryLedger)
            .filter(
                InventoryLedger.workspace_id == workspace_id,
                InventoryLedger.factory_id == factory_id,
                InventoryLedger.item_id == item_id,
                InventoryLedger.inventory_type == inventory_type,
            )
            .order_by(desc(InventoryLedger.performed_at))
            .first()
        )


inventory_ledger_dao = InventoryLedgerDAO(InventoryLedger)
