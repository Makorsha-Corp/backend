"""Work order DAO

SECURITY: All queries MUST filter by workspace_id.
"""
from datetime import date
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session, Query
from sqlalchemy import Date, cast, desc, func, or_
from app.dao.base import BaseDAO
from app.models.work_order import WorkOrder
from app.models.enums import WorkOrderPriorityEnum, WorkOrderStatusEnum
from app.schemas.work_order import WorkOrderCreate, WorkOrderUpdate


def _work_order_calendar_date_expr():
    """SQL: coalesce(planned_date, created_at as date)."""
    return func.coalesce(WorkOrder.planned_date, cast(WorkOrder.created_at, Date))


def _apply_sheet_list_filters(
    query: Query,
    *,
    calendar_date,
    factory_id: Optional[int] = None,
    machine_id: Optional[int] = None,
    planned_date_from: Optional[date] = None,
    planned_date_to: Optional[date] = None,
    status: Optional[WorkOrderStatusEnum] = None,
    status_scope: Optional[str] = None,
    work_order_type_id: Optional[int] = None,
    priority: Optional[WorkOrderPriorityEnum] = None,
    exclude_completed: bool = False,
    search: Optional[str] = None,
) -> Query:
    if factory_id:
        query = query.filter(WorkOrder.factory_id == factory_id)
    if machine_id:
        query = query.filter(WorkOrder.machine_id == machine_id)
    if planned_date_from:
        query = query.filter(calendar_date >= planned_date_from)
    if planned_date_to:
        query = query.filter(calendar_date <= planned_date_to)
    if status_scope == "planned":
        today = date.today()
        query = query.filter(
            WorkOrder.status == WorkOrderStatusEnum.DRAFT.value,
            WorkOrder.planned_date.isnot(None),
            WorkOrder.planned_date > today,
        )
    elif status:
        query = query.filter(WorkOrder.status == status)
    if work_order_type_id:
        query = query.filter(WorkOrder.work_order_type_id == work_order_type_id)
    if priority:
        query = query.filter(WorkOrder.priority == priority)
    if exclude_completed:
        query = query.filter(WorkOrder.status != WorkOrderStatusEnum.COMPLETED.value)
    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(
            or_(
                WorkOrder.work_order_number.ilike(pattern),
                WorkOrder.description.ilike(pattern),
                WorkOrder.assigned_to.ilike(pattern),
            )
        )
    return query


def _sheet_base_query(
    db: Session,
    *,
    workspace_id: int,
    factory_id: Optional[int] = None,
    machine_id: Optional[int] = None,
    planned_date_from: Optional[date] = None,
    planned_date_to: Optional[date] = None,
    status: Optional[WorkOrderStatusEnum] = None,
    status_scope: Optional[str] = None,
    work_order_type_id: Optional[int] = None,
    priority: Optional[WorkOrderPriorityEnum] = None,
    exclude_completed: bool = False,
    search: Optional[str] = None,
) -> Tuple[Query, object]:
    calendar_date = _work_order_calendar_date_expr()
    query = db.query(WorkOrder).filter(
        WorkOrder.workspace_id == workspace_id,
        WorkOrder.is_deleted == False,
        WorkOrder.machine_id.isnot(None),
    )
    query = _apply_sheet_list_filters(
        query,
        calendar_date=calendar_date,
        factory_id=factory_id,
        machine_id=machine_id,
        planned_date_from=planned_date_from,
        planned_date_to=planned_date_to,
        status=status,
        status_scope=status_scope,
        work_order_type_id=work_order_type_id,
        priority=priority,
        exclude_completed=exclude_completed,
        search=search,
    )
    return query, calendar_date


class WorkOrderDAO(BaseDAO[WorkOrder, WorkOrderCreate, WorkOrderUpdate]):
    """DAO for WorkOrder model (workspace-scoped)"""

    def get_by_workspace(
        self, db: Session, *, workspace_id: int,
        work_order_type_id: Optional[int] = None,
        status: Optional[WorkOrderStatusEnum] = None,
        priority: Optional[WorkOrderPriorityEnum] = None,
        factory_id: Optional[int] = None,
        machine_id: Optional[int] = None,
        work_order_template_id: Optional[int] = None,
        planned_date_from: Optional[date] = None,
        planned_date_to: Optional[date] = None,
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
        if work_order_template_id is not None:
            query = query.filter(WorkOrder.work_order_template_id == work_order_template_id)
        if planned_date_from:
            query = query.filter(WorkOrder.planned_date.isnot(None))
            query = query.filter(WorkOrder.planned_date >= planned_date_from)
        if planned_date_to:
            query = query.filter(WorkOrder.planned_date.isnot(None))
            query = query.filter(WorkOrder.planned_date <= planned_date_to)
        return query.order_by(desc(WorkOrder.created_at)).offset(skip).limit(limit).all()

    def list_future_drafts_for_template_machine(
        self,
        db: Session,
        *,
        workspace_id: int,
        work_order_template_id: int,
        machine_id: int,
        after_date: date,
    ) -> List[WorkOrder]:
        """Draft work orders for a recurring program with planned_date strictly after after_date."""
        return (
            db.query(WorkOrder)
            .filter(
                WorkOrder.workspace_id == workspace_id,
                WorkOrder.is_deleted == False,
                WorkOrder.status == WorkOrderStatusEnum.DRAFT.value,
                WorkOrder.work_order_template_id == work_order_template_id,
                WorkOrder.machine_id == machine_id,
                WorkOrder.planned_date.isnot(None),
                WorkOrder.planned_date > after_date,
            )
            .order_by(WorkOrder.planned_date, WorkOrder.id)
            .all()
        )

    def list_drafts_outside_range_for_template_machine(
        self,
        db: Session,
        *,
        workspace_id: int,
        work_order_template_id: int,
        machine_id: int,
        range_start: date,
        range_end: date,
    ) -> List[WorkOrder]:
        """Draft work orders for a recurring program with planned_date outside [range_start, range_end]."""
        return (
            db.query(WorkOrder)
            .filter(
                WorkOrder.workspace_id == workspace_id,
                WorkOrder.is_deleted == False,
                WorkOrder.status == WorkOrderStatusEnum.DRAFT.value,
                WorkOrder.work_order_template_id == work_order_template_id,
                WorkOrder.machine_id == machine_id,
                WorkOrder.planned_date.isnot(None),
                or_(
                    WorkOrder.planned_date < range_start,
                    WorkOrder.planned_date > range_end,
                ),
            )
            .order_by(WorkOrder.planned_date, WorkOrder.id)
            .all()
        )

    def get_by_machine_date_type(
        self,
        db: Session,
        *,
        workspace_id: int,
        machine_id: int,
        planned_date: date,
        work_order_type_id: int,
    ) -> Optional[WorkOrder]:
        """Find an open work order for the same machine + day + work type (sheet merge)."""
        return (
            db.query(WorkOrder)
            .filter(
                WorkOrder.workspace_id == workspace_id,
                WorkOrder.is_deleted == False,
                WorkOrder.machine_id == machine_id,
                WorkOrder.planned_date == planned_date,
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
        planned_date_from: Optional[date] = None,
        planned_date_to: Optional[date] = None,
        status: Optional[WorkOrderStatusEnum] = None,
        status_scope: Optional[str] = None,
        work_order_type_id: Optional[int] = None,
        priority: Optional[WorkOrderPriorityEnum] = None,
        exclude_completed: bool = False,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[WorkOrder]:
        query, calendar_date = _sheet_base_query(
            db,
            workspace_id=workspace_id,
            factory_id=factory_id,
            machine_id=machine_id,
            planned_date_from=planned_date_from,
            planned_date_to=planned_date_to,
            status=status,
            status_scope=status_scope,
            work_order_type_id=work_order_type_id,
            priority=priority,
            exclude_completed=exclude_completed,
            search=search,
        )
        return (
            query.order_by(desc(calendar_date), desc(WorkOrder.created_at))
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count_for_sheet(
        self,
        db: Session,
        *,
        workspace_id: int,
        factory_id: Optional[int] = None,
        machine_id: Optional[int] = None,
        planned_date_from: Optional[date] = None,
        planned_date_to: Optional[date] = None,
        status: Optional[WorkOrderStatusEnum] = None,
        status_scope: Optional[str] = None,
        work_order_type_id: Optional[int] = None,
        priority: Optional[WorkOrderPriorityEnum] = None,
        exclude_completed: bool = False,
        search: Optional[str] = None,
    ) -> int:
        query, _calendar_date = _sheet_base_query(
            db,
            workspace_id=workspace_id,
            factory_id=factory_id,
            machine_id=machine_id,
            planned_date_from=planned_date_from,
            planned_date_to=planned_date_to,
            status=status,
            status_scope=status_scope,
            work_order_type_id=work_order_type_id,
            priority=priority,
            exclude_completed=exclude_completed,
            search=search,
        )
        return query.count()

    def count_by_calendar_date_for_sheet(
        self,
        db: Session,
        *,
        workspace_id: int,
        factory_id: Optional[int] = None,
        machine_id: Optional[int] = None,
        planned_date_from: Optional[date] = None,
        planned_date_to: Optional[date] = None,
        status: Optional[WorkOrderStatusEnum] = None,
        work_order_type_id: Optional[int] = None,
        priority: Optional[WorkOrderPriorityEnum] = None,
    ) -> Dict[date, int]:
        """Count work orders per calendar date for calendar dots (no row limit)."""
        calendar_date = _work_order_calendar_date_expr()
        query = db.query(
            calendar_date,
            func.count(WorkOrder.id),
        ).filter(
            WorkOrder.workspace_id == workspace_id,
            WorkOrder.is_deleted == False,
            WorkOrder.machine_id.isnot(None),
        )
        query = _apply_sheet_list_filters(
            query,
            calendar_date=calendar_date,
            factory_id=factory_id,
            machine_id=machine_id,
            planned_date_from=planned_date_from,
            planned_date_to=planned_date_to,
            status=status,
            work_order_type_id=work_order_type_id,
            priority=priority,
        )
        rows = query.group_by(calendar_date).all()
        return {row[0]: row[1] for row in rows}

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
