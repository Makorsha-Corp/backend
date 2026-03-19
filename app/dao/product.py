"""Product DAO (finished goods)

SECURITY: All queries MUST filter by workspace_id.
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from app.dao.base import BaseDAO
from app.models.product import Product
from app.schemas.product import ProductCreate, ProductUpdate


class ProductDAO(BaseDAO[Product, ProductCreate, ProductUpdate]):
    """DAO for Product model (workspace-scoped)"""

    def get_by_workspace(
        self, db: Session, *, workspace_id: int,
        factory_id: Optional[int] = None,
        is_available_for_sale: Optional[bool] = None,
        skip: int = 0, limit: int = 100
    ) -> List[Product]:
        """Get product records with optional filters."""
        query = db.query(Product).filter(
            Product.workspace_id == workspace_id,
            Product.is_deleted == False,
        )
        if factory_id is not None:
            query = query.filter(Product.factory_id == factory_id)
        if is_available_for_sale is not None:
            query = query.filter(Product.is_available_for_sale == is_available_for_sale)
        return query.offset(skip).limit(limit).all()

    def get_by_id_and_workspace(
        self, db: Session, *, id: int, workspace_id: int
    ) -> Optional[Product]:
        """Get record by ID with workspace isolation."""
        return db.query(Product).filter(
            Product.id == id,
            Product.workspace_id == workspace_id,
        ).first()

    def get_by_factory_item_available(
        self, db: Session, *, factory_id: int, item_id: int,
        is_available_for_sale: bool, workspace_id: int
    ) -> Optional[Product]:
        """Get specific record by factory/item/available combo (unique constraint lookup)."""
        return db.query(Product).filter(
            Product.workspace_id == workspace_id,
            Product.factory_id == factory_id,
            Product.item_id == item_id,
            Product.is_available_for_sale == is_available_for_sale,
            Product.is_deleted == False,
        ).first()

    def get_by_item(
        self, db: Session, *, item_id: int, workspace_id: int
    ) -> List[Product]:
        """Get all product records for an item across factories."""
        return db.query(Product).filter(
            Product.workspace_id == workspace_id,
            Product.item_id == item_id,
            Product.is_deleted == False,
        ).all()

    def soft_delete(self, db: Session, *, db_obj: Product, deleted_by: int) -> Product:
        """Soft delete."""
        from sqlalchemy.sql import func
        db_obj.is_active = False
        db_obj.is_deleted = True
        db_obj.deleted_at = func.now()
        db_obj.deleted_by = deleted_by
        db.add(db_obj)
        db.flush()
        return db_obj

    def restore(self, db: Session, *, db_obj: Product) -> Product:
        """Restore soft-deleted record."""
        db_obj.is_active = True
        db_obj.is_deleted = False
        db_obj.deleted_at = None
        db_obj.deleted_by = None
        db.add(db_obj)
        db.flush()
        return db_obj


product_dao = ProductDAO(Product)
