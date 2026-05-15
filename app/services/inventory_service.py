"""Inventory Service - transaction orchestration for unified inventory"""
from typing import List, Optional
from sqlalchemy.orm import Session

from app.services.base_service import BaseService
from app.managers.inventory_manager import inventory_manager
from app.models.inventory import Inventory
from app.models.enums import InventoryTypeEnum
from app.schemas.inventory import InventoryCreate, InventoryUpdate


class InventoryService(BaseService):
    """Service for inventory workflows. Handles commit/rollback."""

    def __init__(self):
        super().__init__()
        self.manager = inventory_manager

    def create_inventory(
        self, db: Session, inv_in: InventoryCreate,
        workspace_id: int, user_id: int
    ) -> Inventory:
        try:
            record = self.manager.create_inventory(db, data=inv_in, workspace_id=workspace_id, user_id=user_id)
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    def update_inventory(
        self, db: Session, inv_id: int, inv_in: InventoryUpdate,
        workspace_id: int, user_id: int
    ) -> Inventory:
        try:
            record = self.manager.update_inventory(db, inv_id=inv_id, data=inv_in, workspace_id=workspace_id, user_id=user_id)
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    def get_inventory(self, db: Session, inv_id: int, workspace_id: int) -> Inventory:
        return self.manager.get_inventory(db, inv_id, workspace_id)

    def list_inventory(
        self, db: Session, workspace_id: int,
        inventory_type: Optional[InventoryTypeEnum] = None,
        factory_id: Optional[int] = None,
        skip: int = 0, limit: int = 100
    ) -> List[Inventory]:
        return self.manager.list_inventory(
            db, workspace_id=workspace_id,
            inventory_type=inventory_type, factory_id=factory_id,
            skip=skip, limit=limit
        )

    def delete_inventory(self, db: Session, inv_id: int, workspace_id: int, user_id: int) -> Inventory:
        try:
            record = self.manager.delete_inventory(db, inv_id=inv_id, workspace_id=workspace_id, user_id=user_id)
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise


inventory_service = InventoryService()
