"""Work order DAO

SECURITY: All queries MUST filter by workspace_id.
"""
from datetime import date
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.dao.base import BaseDAO
from app.models.work_order import WorkOrder
from app.models.enums import WorkOrderPriorityEnum, WorkOrderStatusEnum
from app.schemas.work_order import WorkOrderCreate, WorkOrderUpdate


class WorkOrderDAO(BaseDAO[WorkOrder, WorkOrderCreate, WorkOrderUpdate]):
    """DAO for WorkOrder model (workspace-scoped)"""

    def get_by_workspace(
        self, db: Session, *, workspace_id: int,
        work_order_type_id: Optional[int] = None,
        status: Optional[WorkOrderStatusEnum] = None,
        priority: Optional[WorkOrderPriorityEnum] = None,
        factory_id: Optional[int] = None,
        machine_id: Optional[int] = None,
        skip: int = 0, limit: int = 100
    ) -> List[WorkOrder]:
        """Get work orders with optional filters."""
        query = db.query(WorkOrder).filter(
            WorkOrder.workspace_id == workspace_id,
            WorkOrder.is_deleted == False,
        )
        if work_order_type_id:
            query = query.filter(WorkOrder.work_order_type_id == work_order_type_id)
        if status:
            query = query.filter(WorkOrder.status == status)
        if priority:
            query = query.filter(WorkOrder.priority == priority)
        if factory_id:
            query = query.filter(WorkOrder.factory_id == factory_id)
        if machine_id:
            query = query.filter(WorkOrder.machine_id == machine_id)
        return query.order_by(desc(WorkOrder.created_at)).offset(skip).limit(limit).all()

    def get_by_machine_date_type(
        self,
        db: Session,
        *,
        workspace_id: int,
        machine_id: int,
        start_date: date,
        work_order_type_id: int,
    ) -> Optional[WorkOrder]:
        """Find an open work order for the same machine + day + work type (sheet merge)."""
        return (
            db.query(WorkOrder)
            .filter(
                WorkOrder.workspace_id == workspace_id,
                WorkOrder.is_deleted == False,
                WorkOrder.machine_id == machine_id,
                WorkOrder.start_date == start_date,
                WorkOrder.work_order_type_id == work_order_type_id,
                WorkOrder.status != WorkOrderStatusEnum.VOIDED.value,
            )
            .order_by(desc(WorkOrder.created_at))
            .first()
        )

    def list_for_sheet(
        self,
        db: Session,
        *,
        workspace_id: int,
        factory_id: Optional[int] = None,
        machine_id: Optional[int] = None,
        start_date_from: Optional[date] = None,
        start_date_to: Optional[date] = None,
        skip: int = 0,
        limit: int = 1000,
    ) -> List[WorkOrder]:
        query = db.query(WorkOrder).filter(
            WorkOrder.workspace_id == workspace_id,
            WorkOrder.is_deleted == False,
            WorkOrder.machine_id.isnot(None),
        )
        if factory_id:
            query = query.filter(WorkOrder.factory_id == factory_id)
        if machine_id:
            query = query.filter(WorkOrder.machine_id == machine_id)
        if start_date_from:
            query = query.filter(WorkOrder.start_date >= start_date_from)
        if start_date_to:
            query = query.filter(WorkOrder.start_date <= start_date_to)
        return (
            query.order_by(desc(WorkOrder.start_date), desc(WorkOrder.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_id_and_workspace(
        self, db: Session, *, id: int, workspace_id: int
    ) -> Optional[WorkOrder]:
        """Get work order by ID with workspace isolation."""
        return db.query(WorkOrder).filter(
            WorkOrder.id == id,
            WorkOrder.workspace_id == workspace_id,
        ).first()

    def get_next_number(self, db: Session, *, workspace_id: int) -> str:
        """Generate next work order number (WO-2025-001)."""
        from datetime import datetime
        year = datetime.now().year
        prefix = f"WO-{year}-"
        last = db.query(WorkOrder).filter(
            WorkOrder.workspace_id == workspace_id,
            WorkOrder.work_order_number.like(f"{prefix}%"),
        ).order_by(desc(WorkOrder.work_order_number)).first()
        if last:
            try:
                last_num = int(last.work_order_number.split("-")[-1])
                return f"{prefix}{last_num + 1:03d}"
            except (ValueError, IndexError):
                pass
        return f"{prefix}001"

    def soft_delete(self, db: Session, *, db_obj: WorkOrder, deleted_by: int) -> WorkOrder:
        """Soft delete."""
        from sqlalchemy.sql import func
        db_obj.is_active = False
        db_obj.is_deleted = True
        db_obj.deleted_at = func.now()
        db_obj.deleted_by = deleted_by
        db.add(db_obj)
        db.flush()
        return db_obj

    def restore(self, db: Session, *, db_obj: WorkOrder) -> WorkOrder:
        """Restore soft-deleted record."""
        db_obj.is_active = True
        db_obj.is_deleted = False
        db_obj.deleted_at = None
        db_obj.deleted_by = None
        db.add(db_obj)
        db.flush()
        return db_obj


work_order_dao = WorkOrderDAO(WorkOrder)
