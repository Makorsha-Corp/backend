"""Product ledger DAO

SECURITY: All queries MUST filter by workspace_id.
"""
from datetime import datetime

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.dao.base import BaseDAO
from app.models.product_ledger import ProductLedger
from app.schemas.product_ledger import ProductLedgerCreate, ProductLedgerUpdate


class ProductLedgerDAO(BaseDAO[ProductLedger, ProductLedgerCreate, ProductLedgerUpdate]):
    """DAO for ProductLedger model (workspace-scoped)"""

    def get_by_workspace(
        self, db: Session, *, workspace_id: int,
        factory_id: int | None = None,
        item_id: int | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        transaction_type: str | None = None,
        skip: int = 0, limit: int = 100,
    ) -> list[ProductLedger]:
        """Get ledger entries with optional filters, newest first.

        All filters are AND-combined and all are optional except workspace_id.
        """
        query = db.query(ProductLedger).filter(
            ProductLedger.workspace_id == workspace_id,
        )
        if factory_id is not None:
            query = query.filter(ProductLedger.factory_id == factory_id)
        if item_id is not None:
            query = query.filter(ProductLedger.item_id == item_id)
        if start_date is not None:
            query = query.filter(ProductLedger.performed_at >= start_date)
        if end_date is not None:
            query = query.filter(ProductLedger.performed_at <= end_date)
        if transaction_type:
            query = query.filter(ProductLedger.transaction_type == transaction_type)
        return query.order_by(desc(ProductLedger.performed_at)).offset(skip).limit(limit).all()

    def exists_for_production_batch(
        self, db: Session, *, workspace_id: int, batch_id: int
    ) -> bool:
        """True if any product ledger row was created from this production batch."""
        return (
            db.query(ProductLedger.id)
            .filter(
                ProductLedger.workspace_id == workspace_id,
                ProductLedger.source_type == "production_batch",
                ProductLedger.source_id == batch_id,
            )
            .first()
            is not None
        )

    def get_by_id_and_workspace(
        self, db: Session, *, id: int, workspace_id: int
    ) -> ProductLedger | None:
        """Get ledger entry by ID with workspace isolation."""
        return db.query(ProductLedger).filter(
            ProductLedger.id == id,
            ProductLedger.workspace_id == workspace_id,
        ).first()


product_ledger_dao = ProductLedgerDAO(ProductLedger)
