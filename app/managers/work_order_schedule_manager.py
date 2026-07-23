"""Business logic for staged work order schedules."""
from datetime import date, datetime
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
from app.utils.work_order_generation import resolve_template_machine_ids
from app.utils.work_order_recurrence import advance_next_generation_date, should_advance_template


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
        recurring = [
            tpl for tpl in recurring
            if getattr(tpl, 'generation_mode', 'schedule') == 'schedule'
        ]

        seen_tpl_ids: set[int] = set()
        templates: List[WorkOrderTemplate] = []
        for tpl in recurring:
            if tpl.id in seen_tpl_ids:
                continue
            seen_tpl_ids.add(tpl.id)
            templates.append(tpl)

        created: List[WorkOrderSchedule] = []
        for tpl in templates:
            machine_ids = resolve_template_machine_ids(
                session,
                template=tpl,
                workspace_id=workspace_id,
                factory_section_id=factory_section_id,
                factory_id=factory_id,
            )

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
                    planned_date=target_date,
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

            if should_advance_template(tpl, target_date):
                tpl.next_generation_date = advance_next_generation_date(
                    from_date=target_date,
                    recurrence_type=tpl.recurrence_type,
                    recurrence_day=tpl.recurrence_day,
                )
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
                    planned_date=record.scheduled_date,
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
                    planned_date=record.scheduled_date,
                    assigned_to=record.assigned_to,
                ),
                workspace_id=workspace_id,
                user_id=user_id,
            )

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
