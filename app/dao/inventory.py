"""Unified inventory DAO (STORAGE, DAMAGED, WASTE, SCRAP)

SECURITY: All queries MUST filter by workspace_id.
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.dao.base import BaseDAO
from app.models.inventory import Inventory
from app.models.enums import InventoryTypeEnum
from app.schemas.inventory import InventoryCreate, InventoryUpdate


class InventoryDAO(BaseDAO[Inventory, InventoryCreate, InventoryUpdate]):
    """DAO for unified Inventory model (workspace-scoped)"""

    def get_by_workspace(
        self, db: Session, *, workspace_id: int,
        inventory_type: Optional[InventoryTypeEnum] = None,
        factory_id: Optional[int] = None,
        skip: int = 0, limit: int = 100
    ) -> List[Inventory]:
        """Get inventory records with optional type/factory filter."""
        query = db.query(Inventory).filter(
            Inventory.workspace_id == workspace_id,
            Inventory.is_deleted == False,
        )
        if inventory_type:
            query = query.filter(Inventory.inventory_type == inventory_type)
        if factory_id:
            query = query.filter(Inventory.factory_id == factory_id)
        return query.offset(skip).limit(limit).all()

    def get_by_id_and_workspace(
        self, db: Session, *, id: int, workspace_id: int
    ) -> Optional[Inventory]:
        """Get record by ID with workspace isolation."""
        return db.query(Inventory).filter(
            Inventory.id == id,
            Inventory.workspace_id == workspace_id,
        ).first()

    def get_by_factory_item_type(
        self, db: Session, *, factory_id: int, item_id: int,
        inventory_type: InventoryTypeEnum, workspace_id: int
    ) -> Optional[Inventory]:
        """Get specific record by factory/item/type combo (unique constraint lookup)."""
        return db.query(Inventory).filter(
            Inventory.workspace_id == workspace_id,
            Inventory.factory_id == factory_id,
            Inventory.item_id == item_id,
            Inventory.inventory_type == inventory_type,
            Inventory.is_deleted == False,
        ).first()

    def get_by_item(
        self, db: Session, *, item_id: int, workspace_id: int,
        inventory_type: Optional[InventoryTypeEnum] = None
    ) -> List[Inventory]:
        """Get all records for an item across factories."""
        query = db.query(Inventory).filter(
            Inventory.workspace_id == workspace_id,
            Inventory.item_id == item_id,
            Inventory.is_deleted == False,
        )
        if inventory_type:
            query = query.filter(Inventory.inventory_type == inventory_type)
        return query.all()

    def soft_delete(self, db: Session, *, db_obj: Inventory, deleted_by: int) -> Inventory:
        """Soft delete."""
        from sqlalchemy.sql import func
        db_obj.is_active = False
        db_obj.is_deleted = True
        db_obj.deleted_at = func.now()
        db_obj.deleted_by = deleted_by
        db.add(db_obj)
        db.flush()
        return db_obj

    def restore(self, db: Session, *, db_obj: Inventory) -> Inventory:
        """Restore soft-deleted record."""
        db_obj.is_active = True
        db_obj.is_deleted = False
        db_obj.deleted_at = None
        db_obj.deleted_by = None
        db.add(db_obj)
        db.flush()
        return db_obj


inventory_dao = InventoryDAO(Inventory)
