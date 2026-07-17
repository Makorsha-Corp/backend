"""Work order schedule service — transaction boundaries."""
from datetime import date
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session

from app.services.base_service import BaseService
from app.managers.work_order_schedule_manager import work_order_schedule_manager
from app.models.work_order_schedule import WorkOrderSchedule
from app.models.work_order import WorkOrder
from app.models.enums import WorkOrderScheduleStatusEnum
from app.schemas.work_order_schedule import StageWorkOrderDayRequest, WorkOrderScheduleResponse
from app.dao.machine import machine_dao
from app.dao.work_order_template import work_order_template_dao
from app.dao.work_order_type import work_order_type_dao


class WorkOrderScheduleService(BaseService):
    def __init__(self):
        self.manager = work_order_schedule_manager

    def _to_response(self, db: Session, record: WorkOrderSchedule, workspace_id: int) -> WorkOrderScheduleResponse:
        machine = machine_dao.get_by_id_and_workspace(db, id=record.machine_id, workspace_id=workspace_id)
        wo_type = work_order_type_dao.get_by_id_and_workspace(
            db, id=record.work_order_type_id, workspace_id=workspace_id,
        )
        template_name = None
        if record.work_order_template_id:
            tpl = work_order_template_dao.get_by_id_and_workspace(
                db, id=record.work_order_template_id, workspace_id=workspace_id,
            )
            template_name = tpl.template_name if tpl else None
        return WorkOrderScheduleResponse(
            id=record.id,
            workspace_id=record.workspace_id,
            scheduled_date=record.scheduled_date,
            status=record.status,
            work_order_template_id=record.work_order_template_id,
            template_name=template_name,
            machine_id=record.machine_id,
            machine_name=machine.name if machine else None,
            factory_id=record.factory_id,
            factory_section_id=record.factory_section_id,
            work_order_type_id=record.work_order_type_id,
            work_order_type_name=wo_type.name if wo_type else None,
            title=record.title,
            description=record.description,
            priority=record.priority,
            assigned_to=record.assigned_to,
            work_order_id=record.work_order_id,
            confirmed_at=record.confirmed_at,
            confirmed_by=record.confirmed_by,
            cancelled_at=record.cancelled_at,
            cancelled_by=record.cancelled_by,
            created_at=record.created_at,
            created_by=record.created_by,
        )

    def list_schedules(
        self,
        db: Session,
        *,
        workspace_id: int,
        factory_id: Optional[int] = None,
        machine_id: Optional[int] = None,
        start_date_from: Optional[date] = None,
        start_date_to: Optional[date] = None,
        status: Optional[WorkOrderScheduleStatusEnum] = None,
        skip: int = 0,
        limit: int = 1000,
    ) -> List[WorkOrderScheduleResponse]:
        records = self.manager.list_schedules(
            db,
            workspace_id=workspace_id,
            factory_id=factory_id,
            machine_id=machine_id,
            start_date_from=start_date_from,
            start_date_to=start_date_to,
            status=status,
            skip=skip,
            limit=limit,
        )
        return [self._to_response(db, r, workspace_id) for r in records]

    def stage_day(
        self, db: Session, body: StageWorkOrderDayRequest, workspace_id: int, user_id: int,
    ) -> List[WorkOrderScheduleResponse]:
        try:
            records = self.manager.stage_day(
                db, body=body, workspace_id=workspace_id, user_id=user_id,
            )
            self._commit_transaction(db)
            for r in records:
                db.refresh(r)
            return [self._to_response(db, r, workspace_id) for r in records]
        except Exception:
            self._rollback_transaction(db)
            raise

    def confirm_schedule(
        self, db: Session, schedule_id: int, workspace_id: int, user_id: int,
    ) -> Tuple[WorkOrder, WorkOrderScheduleResponse]:
        try:
            wo, record = self.manager.confirm_schedule(
                db, schedule_id=schedule_id, workspace_id=workspace_id, user_id=user_id,
            )
            self._commit_transaction(db)
            db.refresh(wo)
            db.refresh(record)
            return wo, self._to_response(db, record, workspace_id)
        except Exception:
            self._rollback_transaction(db)
            raise

    def cancel_schedule(
        self, db: Session, schedule_id: int, workspace_id: int, user_id: int,
    ) -> WorkOrderScheduleResponse:
        try:
            record = self.manager.cancel_schedule(
                db, schedule_id=schedule_id, workspace_id=workspace_id, user_id=user_id,
            )
            self._commit_transaction(db)
            db.refresh(record)
            return self._to_response(db, record, workspace_id)
        except Exception:
            self._rollback_transaction(db)
            raise


work_order_schedule_service = WorkOrderScheduleService()
