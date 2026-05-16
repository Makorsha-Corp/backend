"""Product Service - transaction orchestration for finished goods"""
from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session

from app.services.base_service import BaseService
from app.managers.product_manager import product_manager
from app.models.product import Product
from app.models.product_ledger import ProductLedger
from app.schemas.product import ProductCreate, ProductUpdate
from app.dao.product_ledger import product_ledger_dao


class ProductService(BaseService):
    """Service for product workflows. Handles commit/rollback."""

    def __init__(self):
        super().__init__()
        self.manager = product_manager
        self.ledger_dao = product_ledger_dao

    def create_product(
        self, db: Session, prod_in: ProductCreate,
        workspace_id: int, user_id: int
    ) -> Product:
        try:
            record = self.manager.create_product(db, data=prod_in, workspace_id=workspace_id, user_id=user_id)
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    def update_product(
        self, db: Session, prod_id: int, prod_in: ProductUpdate,
        workspace_id: int, user_id: int
    ) -> Product:
        try:
            record = self.manager.update_product(db, prod_id=prod_id, data=prod_in, workspace_id=workspace_id, user_id=user_id)
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    def get_product(self, db: Session, prod_id: int, workspace_id: int) -> Product:
        return self.manager.get_product(db, prod_id, workspace_id)

    def list_products(
        self, db: Session, workspace_id: int,
        factory_id: Optional[int] = None,
        is_available_for_sale: Optional[bool] = None,
        skip: int = 0, limit: int = 100
    ) -> List[Product]:
        return self.manager.list_products(
            db, workspace_id=workspace_id,
            factory_id=factory_id,
            is_available_for_sale=is_available_for_sale,
            skip=skip, limit=limit
        )

    def delete_product(self, db: Session, prod_id: int, workspace_id: int, user_id: int) -> Product:
        try:
            record = self.manager.delete_product(db, prod_id=prod_id, workspace_id=workspace_id, user_id=user_id)
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    # Ledger queries
    def list_ledger(
        self, db: Session, workspace_id: int,
        factory_id: Optional[int] = None,
        item_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        transaction_type: Optional[str] = None,
        skip: int = 0, limit: int = 100,
    ) -> List[ProductLedger]:
        return self.ledger_dao.get_by_workspace(
            db, workspace_id=workspace_id,
            factory_id=factory_id,
            item_id=item_id,
            start_date=start_date,
            end_date=end_date,
            transaction_type=transaction_type,
            skip=skip, limit=limit,
        )


product_service = ProductService()
