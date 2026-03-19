"""Unified inventory ledger DAO

SECURITY: All queries MUST filter by workspace_id.
"""
from typing import List, Optional
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


inventory_ledger_dao = InventoryLedgerDAO(InventoryLedger)
