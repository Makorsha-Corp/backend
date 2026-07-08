"""Work Order Service - transaction orchestration"""
from typing import List, Optional
from sqlalchemy.orm import Session

from app.services.base_service import BaseService
from app.managers.work_order_manager import work_order_manager
from app.models.work_order import WorkOrder
from app.models.work_order_item import WorkOrderItem
from app.models.enums import WorkTypeEnum, WorkOrderPriorityEnum, WorkOrderStatusEnum
from app.schemas.work_order import WorkOrderCreate, WorkOrderUpdate
from app.schemas.work_order_item import WorkOrderItemCreate, WorkOrderItemUpdate


class WorkOrderService(BaseService):
    """Service for work order workflows. Handles commit/rollback."""

    def __init__(self):
        super().__init__()
        self.manager = work_order_manager

    def create_work_order(
        self, db: Session, wo_in: WorkOrderCreate,
        workspace_id: int, user_id: int
    ) -> WorkOrder:
        try:
            record = self.manager.create_work_order(db, data=wo_in, workspace_id=workspace_id, user_id=user_id)
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    def update_work_order(
        self, db: Session, wo_id: int, wo_in: WorkOrderUpdate,
        workspace_id: int, user_id: int
    ) -> WorkOrder:
        try:
            record = self.manager.update_work_order(db, wo_id=wo_id, data=wo_in, workspace_id=workspace_id, user_id=user_id)
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    def get_work_order(self, db: Session, wo_id: int, workspace_id: int) -> WorkOrder:
        return self.manager.get_work_order(db, wo_id, workspace_id)

    def list_work_orders(
        self, db: Session, workspace_id: int,
        work_type: Optional[WorkTypeEnum] = None,
        wo_status: Optional[WorkOrderStatusEnum] = None,
        priority: Optional[WorkOrderPriorityEnum] = None,
        factory_id: Optional[int] = None,
        machine_id: Optional[int] = None,
        skip: int = 0, limit: int = 100
    ) -> List[WorkOrder]:
        return self.manager.list_work_orders(
            db, workspace_id=workspace_id,
            work_type=work_type, wo_status=wo_status, priority=priority,
            factory_id=factory_id, machine_id=machine_id,
            skip=skip, limit=limit
        )

    def delete_work_order(self, db: Session, wo_id: int, workspace_id: int, user_id: int) -> WorkOrder:
        try:
            record = self.manager.delete_work_order(db, wo_id=wo_id, workspace_id=workspace_id, user_id=user_id)
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    # ─── Work Order Items ───────────────────────────────────────
    def add_item(
        self, db: Session, item_in: WorkOrderItemCreate,
        workspace_id: int, user_id: int
    ) -> WorkOrderItem:
        try:
            record = self.manager.add_item(db, data=item_in, workspace_id=workspace_id, user_id=user_id)
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    def update_item(
        self, db: Session, item_id: int, item_in: WorkOrderItemUpdate,
        workspace_id: int
    ) -> WorkOrderItem:
        try:
            record = self.manager.update_item(db, item_id=item_id, data=item_in, workspace_id=workspace_id)
            self._commit_transaction(db)
            db.refresh(record)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    def remove_item(self, db: Session, item_id: int, workspace_id: int) -> WorkOrderItem:
        try:
            record = self.manager.remove_item(db, item_id=item_id, workspace_id=workspace_id)
            self._commit_transaction(db)
            return record
        except Exception:
            self._rollback_transaction(db)
            raise

    def get_items(self, db: Session, wo_id: int, workspace_id: int) -> List[WorkOrderItem]:
        return self.manager.get_items(db, wo_id, workspace_id)


work_order_service = WorkOrderService()
