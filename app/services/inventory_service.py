"""Inventory Service - transaction orchestration for unified inventory"""
from typing import List, Optional
from sqlalchemy.orm import Session

from app.services.base_service import BaseService
from app.managers.inventory_manager import inventory_manager
from app.models.inventory import Inventory
from app.models.enums import InventoryTypeEnum
from app.schemas.inventory import InventoryCreate, InventoryUpdate, InventoryListResponse, InventoryStatsResponse
from app.schemas.inventory_incoming import ItemIncomingSummary


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

    def get_inventory_page(
        self,
        db: Session,
        *,
        workspace_id: int,
        inventory_type: Optional[InventoryTypeEnum] = None,
        factory_id: Optional[int] = None,
        item_id: Optional[int] = None,
        search: Optional[str] = None,
        include_zero_qty: bool = False,
        skip: int = 0,
        limit: int = 50,
    ) -> InventoryListResponse:
        return self.manager.get_inventory_page(
            db,
            workspace_id=workspace_id,
            inventory_type=inventory_type,
            factory_id=factory_id,
            item_id=item_id,
            search=search,
            include_zero_qty=include_zero_qty,
            skip=skip,
            limit=limit,
        )

    def get_inventory_stats(
        self,
        db: Session,
        *,
        workspace_id: int,
        inventory_type: Optional[InventoryTypeEnum] = None,
        factory_id: Optional[int] = None,
        item_id: Optional[int] = None,
        search: Optional[str] = None,
        include_zero_qty: bool = False,
    ) -> InventoryStatsResponse:
        return self.manager.get_inventory_stats(
            db,
            workspace_id=workspace_id,
            inventory_type=inventory_type,
            factory_id=factory_id,
            item_id=item_id,
            search=search,
            include_zero_qty=include_zero_qty,
        )

    def get_incoming_summary(
        self, db: Session, *, workspace_id: int, factory_id: Optional[int] = None
    ) -> List[ItemIncomingSummary]:
        return self.manager.get_incoming_summary(
            session=db, workspace_id=workspace_id, factory_id=factory_id
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
