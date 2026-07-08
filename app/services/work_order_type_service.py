"""Work Order Type Service for orchestrating work order type workflows"""
from typing import List, Optional
from sqlalchemy.orm import Session

from app.services.base_service import BaseService
from app.managers.work_order_type_manager import work_order_type_manager
from app.models.work_order_type import WorkOrderType
from app.schemas.work_order_type import WorkOrderTypeCreate, WorkOrderTypeUpdate


class WorkOrderTypeService(BaseService):
    """Service for WorkOrderType workflows. Handles commit/rollback."""

    def __init__(self):
        super().__init__()
        self.manager = work_order_type_manager

    def create_work_order_type(
        self, db: Session, type_in: WorkOrderTypeCreate, workspace_id: int, user_id: int
    ) -> WorkOrderType:
        try:
            wo_type = self.manager.create_work_order_type(
                session=db, type_data=type_in, workspace_id=workspace_id, user_id=user_id
            )
            self._commit_transaction(db)
            db.refresh(wo_type)
            return wo_type
        except Exception:
            self._rollback_transaction(db)
            raise

    def get_work_order_type(self, db: Session, type_id: int, workspace_id: int) -> WorkOrderType:
        return self.manager.get_work_order_type(db, type_id, workspace_id)

    def get_work_order_types(
        self, db: Session, workspace_id: int,
        search: Optional[str] = None, skip: int = 0, limit: int = 100
    ) -> List[WorkOrderType]:
        return self.manager.search_work_order_types(
            session=db, workspace_id=workspace_id, search=search, skip=skip, limit=limit
        )

    def update_work_order_type(
        self, db: Session, type_id: int, type_in: WorkOrderTypeUpdate, workspace_id: int, user_id: int
    ) -> WorkOrderType:
        try:
            wo_type = self.manager.update_work_order_type(
                session=db, type_id=type_id, type_data=type_in, workspace_id=workspace_id, user_id=user_id
            )
            self._commit_transaction(db)
            db.refresh(wo_type)
            return wo_type
        except Exception:
            self._rollback_transaction(db)
            raise

    def delete_work_order_type(self, db: Session, type_id: int, workspace_id: int, user_id: int) -> WorkOrderType:
        try:
            wo_type = self.manager.delete_work_order_type(
                session=db, type_id=type_id, workspace_id=workspace_id, user_id=user_id
            )
            self._commit_transaction(db)
            db.refresh(wo_type)
            return wo_type
        except Exception:
            self._rollback_transaction(db)
            raise


# Singleton instance
work_order_type_service = WorkOrderTypeService()
