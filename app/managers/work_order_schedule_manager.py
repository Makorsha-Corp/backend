"""Business logic for staged work order schedules."""
from datetime import date, timedelta
from typing import List, Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.dao.work_order_schedule import work_order_schedule_dao
from app.dao.machine import machine_dao
from app.dao.work_order import work_order_dao
from app.dao.work_order_template import work_order_template_dao
from app.managers.work_order_manager import work_order_manager
from app.models.work_order_schedule import WorkOrderSchedule
from app.models.work_order_template import WorkOrderTemplate
from app.models.enums import WorkOrderScheduleStatusEnum
from app.schemas.work_order_schedule import StageWorkOrderDayRequest
from app.schemas.work_order_template import WorkOrderFromTemplateCreate


class WorkOrderScheduleManager:
    def _resolve_names(
        self, session: Session, record: WorkOrderSchedule, workspace_id: int,
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        machine = machine_dao.get_by_id_and_workspace(session, id=record.machine_id, workspace_id=workspace_id)
        machine_name = machine.name if machine else None
        type_name = None
        if record.work_order_type_id:
            from app.dao.work_order_type import work_order_type_dao
            wo_type = work_order_type_dao.get_by_id_and_workspace(
                session, id=record.work_order_type_id, workspace_id=workspace_id,
            )
            type_name = wo_type.name if wo_type else None
        template_name = None
        if record.work_order_template_id:
            tpl = work_order_template_dao.get_by_id_and_workspace(
                session, id=record.work_order_template_id, workspace_id=workspace_id,
            )
            template_name = tpl.template_name if tpl else None
        return machine_name, type_name, template_name

    def list_schedules(
        self,
        session: Session,
        *,
        workspace_id: int,
        factory_id: Optional[int] = None,
        machine_id: Optional[int] = None,
        start_date_from: Optional[date] = None,
        start_date_to: Optional[date] = None,
        status: Optional[WorkOrderScheduleStatusEnum] = None,
        skip: int = 0,
        limit: int = 1000,
    ) -> List[WorkOrderSchedule]:
        statuses = [status] if status else [
            WorkOrderScheduleStatusEnum.STAGED,
            WorkOrderScheduleStatusEnum.CONFIRMED,
        ]
        return work_order_schedule_dao.list_for_sheet(
            session,
            workspace_id=workspace_id,
            factory_id=factory_id,
            machine_id=machine_id,
            start_date_from=start_date_from,
            start_date_to=start_date_to,
            statuses=statuses,
            skip=skip,
            limit=limit,
        )

    def stage_day(
        self,
        session: Session,
        *,
        body: StageWorkOrderDayRequest,
        workspace_id: int,
        user_id: int,
    ) -> List[WorkOrderSchedule]:
        target_date = body.target_date
        factory_section_id = body.factory_section_id
        factory_id = body.factory_id

        recurring = work_order_template_dao.list_recurring_due(
            session,
            workspace_id=workspace_id,
            target_date=target_date,
            factory_section_id=factory_section_id,
            factory_id=factory_id,
        )

        seen_tpl_ids: set[int] = set()
        templates: List[WorkOrderTemplate] = []
        for tpl in recurring:
            if tpl.id in seen_tpl_ids:
                continue
            seen_tpl_ids.add(tpl.id)
            templates.append(tpl)

        created: List[WorkOrderSchedule] = []
        for tpl in templates:
            machine_ids: List[int] = []
            section_id = tpl.default_factory_section_id or factory_section_id
            if tpl.default_machine_id:
                machine_ids = [tpl.default_machine_id]
            elif section_id:
                machines = machine_dao.get_by_section(
                    session, factory_section_id=section_id, workspace_id=workspace_id, limit=1000,
                )
                machine_ids = [m.id for m in machines]
            elif factory_section_id:
                machines = machine_dao.get_by_section(
                    session, factory_section_id=factory_section_id, workspace_id=workspace_id, limit=1000,
                )
                machine_ids = [m.id for m in machines]
            elif factory_id:
                machines = machine_dao.get_by_factory(
                    session, factory_id=factory_id, workspace_id=workspace_id, limit=1000,
                )
                machine_ids = [m.id for m in machines]

            type_name = tpl.work_order_type_name or 'Maintenance'
            for mid in machine_ids:
                if work_order_schedule_dao.find_staged(
                    session,
                    workspace_id=workspace_id,
                    machine_id=mid,
                    scheduled_date=target_date,
                    work_order_type_id=tpl.work_order_type_id,
                ):
                    continue
                existing_wo = work_order_dao.get_by_machine_date_type(
                    session,
                    workspace_id=workspace_id,
                    machine_id=mid,
                    start_date=target_date,
                    work_order_type_id=tpl.work_order_type_id,
                )
                if existing_wo:
                    continue

                machine = machine_dao.get_by_id_and_workspace(session, id=mid, workspace_id=workspace_id)
                if not machine:
                    continue
                resolved_factory_id = machine.factory_id
                if factory_id and resolved_factory_id != factory_id:
                    continue

                schedule = WorkOrderSchedule(
                    workspace_id=workspace_id,
                    scheduled_date=target_date,
                    status=WorkOrderScheduleStatusEnum.STAGED,
                    work_order_template_id=tpl.id,
                    machine_id=mid,
                    factory_id=resolved_factory_id,
                    factory_section_id=machine.factory_section_id,
                    work_order_type_id=tpl.work_order_type_id,
                    title=f'{type_name} — {machine.name}',
                    description=tpl.description,
                    priority=tpl.priority,
                    assigned_to=tpl.assigned_to,
                    created_by=user_id,
                )
                session.add(schedule)
                session.flush()
                created.append(schedule)

            if tpl.is_recurring and tpl.next_generation_date is not None and tpl.next_generation_date <= target_date:
                if tpl.recurrence_type == 'daily':
                    tpl.next_generation_date = target_date + timedelta(days=1)
                elif tpl.recurrence_type == 'weekly':
                    tpl.next_generation_date = target_date + timedelta(days=7)
                elif tpl.recurrence_type == 'monthly':
                    tpl.next_generation_date = target_date + timedelta(days=28)
                else:
                    tpl.next_generation_date = target_date + timedelta(days=1)
                session.flush()

        return created

    def confirm_schedule(
        self,
        session: Session,
        *,
        schedule_id: int,
        workspace_id: int,
        user_id: int,
    ):
        from app.models.work_order import WorkOrder

        record = work_order_schedule_dao.get_by_id_and_workspace(
            session, id=schedule_id, workspace_id=workspace_id,
        )
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Schedule not found')
        if record.status != WorkOrderScheduleStatusEnum.STAGED:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Only staged schedules can be confirmed')

        if record.work_order_template_id:
            wo = work_order_manager.create_work_order_from_template(
                session,
                template_id=record.work_order_template_id,
                workspace_id=workspace_id,
                user_id=user_id,
                overrides=WorkOrderFromTemplateCreate(
                    machine_id=record.machine_id,
                    start_date=record.scheduled_date,
                    title=record.title,
                    description=record.description,
                    assigned_to=record.assigned_to,
                ),
            )
        else:
            from app.schemas.work_order import WorkOrderCreate
            wo = work_order_manager.create_work_order(
                session,
                data=WorkOrderCreate(
                    work_order_type_id=record.work_order_type_id,
                    title=record.title,
                    description=record.description,
                    priority=record.priority,
                    factory_id=record.factory_id,
                    machine_id=record.machine_id,
                    start_date=record.scheduled_date,
                    assigned_to=record.assigned_to,
                ),
                workspace_id=workspace_id,
                user_id=user_id,
            )

        from datetime import datetime
        record.status = WorkOrderScheduleStatusEnum.CONFIRMED
        record.work_order_id = wo.id
        record.confirmed_at = datetime.utcnow()
        record.confirmed_by = user_id
        session.flush()
        return wo, record

    def cancel_schedule(
        self,
        session: Session,
        *,
        schedule_id: int,
        workspace_id: int,
        user_id: int,
    ) -> WorkOrderSchedule:
        from datetime import datetime

        record = work_order_schedule_dao.get_by_id_and_workspace(
            session, id=schedule_id, workspace_id=workspace_id,
        )
        if not record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Schedule not found')
        if record.status != WorkOrderScheduleStatusEnum.STAGED:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Only staged schedules can be cancelled')

        record.status = WorkOrderScheduleStatusEnum.CANCELLED
        record.cancelled_at = datetime.utcnow()
        record.cancelled_by = user_id
        session.flush()
        return record


work_order_schedule_manager = WorkOrderScheduleManager()
