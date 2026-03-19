"""Product ledger DAO

SECURITY: All queries MUST filter by workspace_id.
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.dao.base import BaseDAO
from app.models.product_ledger import ProductLedger
from app.schemas.product_ledger import ProductLedgerCreate, ProductLedgerUpdate


class ProductLedgerDAO(BaseDAO[ProductLedger, ProductLedgerCreate, ProductLedgerUpdate]):
    """DAO for ProductLedger model (workspace-scoped)"""

    def get_by_workspace(
        self, db: Session, *, workspace_id: int,
        factory_id: Optional[int] = None,
        item_id: Optional[int] = None,
        skip: int = 0, limit: int = 100
    ) -> List[ProductLedger]:
        """Get ledger entries with optional filters, newest first."""
        query = db.query(ProductLedger).filter(
            ProductLedger.workspace_id == workspace_id,
        )
        if factory_id:
            query = query.filter(ProductLedger.factory_id == factory_id)
        if item_id:
            query = query.filter(ProductLedger.item_id == item_id)
        return query.order_by(desc(ProductLedger.performed_at)).offset(skip).limit(limit).all()

    def get_by_id_and_workspace(
        self, db: Session, *, id: int, workspace_id: int
    ) -> Optional[ProductLedger]:
        """Get ledger entry by ID with workspace isolation."""
        return db.query(ProductLedger).filter(
            ProductLedger.id == id,
            ProductLedger.workspace_id == workspace_id,
        ).first()


product_ledger_dao = ProductLedgerDAO(ProductLedger)
