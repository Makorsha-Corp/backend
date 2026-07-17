"""Work order schedule DAO."""
from datetime import date
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.dao.base import BaseDAO
from app.models.work_order_schedule import WorkOrderSchedule
from app.models.enums import WorkOrderScheduleStatusEnum


class WorkOrderScheduleDAO(BaseDAO[WorkOrderSchedule, dict, dict]):
    def get_by_id_and_workspace(
        self, db: Session, *, id: int, workspace_id: int,
    ) -> Optional[WorkOrderSchedule]:
        return db.query(WorkOrderSchedule).filter(
            WorkOrderSchedule.id == id,
            WorkOrderSchedule.workspace_id == workspace_id,
        ).first()

    def find_staged(
        self,
        db: Session,
        *,
        workspace_id: int,
        machine_id: int,
        scheduled_date: date,
        work_order_type_id: int,
    ) -> Optional[WorkOrderSchedule]:
        return db.query(WorkOrderSchedule).filter(
            WorkOrderSchedule.workspace_id == workspace_id,
            WorkOrderSchedule.machine_id == machine_id,
            WorkOrderSchedule.scheduled_date == scheduled_date,
            WorkOrderSchedule.work_order_type_id == work_order_type_id,
            WorkOrderSchedule.status == WorkOrderScheduleStatusEnum.STAGED,
        ).first()

    def list_for_sheet(
        self,
        db: Session,
        *,
        workspace_id: int,
        factory_id: Optional[int] = None,
        machine_id: Optional[int] = None,
        start_date_from: Optional[date] = None,
        start_date_to: Optional[date] = None,
        statuses: Optional[List[WorkOrderScheduleStatusEnum]] = None,
        skip: int = 0,
        limit: int = 1000,
    ) -> List[WorkOrderSchedule]:
        query = db.query(WorkOrderSchedule).filter(
            WorkOrderSchedule.workspace_id == workspace_id,
        )
        if factory_id:
            query = query.filter(WorkOrderSchedule.factory_id == factory_id)
        if machine_id:
            query = query.filter(WorkOrderSchedule.machine_id == machine_id)
        if start_date_from:
            query = query.filter(WorkOrderSchedule.scheduled_date >= start_date_from)
        if start_date_to:
            query = query.filter(WorkOrderSchedule.scheduled_date <= start_date_to)
        if statuses:
            query = query.filter(WorkOrderSchedule.status.in_(statuses))
        return (
            query.order_by(desc(WorkOrderSchedule.scheduled_date), WorkOrderSchedule.id)
            .offset(skip)
            .limit(limit)
            .all()
        )


work_order_schedule_dao = WorkOrderScheduleDAO(WorkOrderSchedule)
