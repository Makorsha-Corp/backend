"""Work order schedule schemas"""
from datetime import date, datetime
from pydantic import BaseModel, ConfigDict
from app.models.enums import WorkOrderPriorityEnum, WorkOrderScheduleStatusEnum


class WorkOrderScheduleResponse(BaseModel):
    id: int
    workspace_id: int
    scheduled_date: date
    status: WorkOrderScheduleStatusEnum
    work_order_template_id: int | None = None
    template_name: str | None = None
    machine_id: int
    machine_name: str | None = None
    factory_id: int
    factory_section_id: int | None = None
    work_order_type_id: int
    work_order_type_name: str | None = None
    title: str
    description: str | None = None
    priority: WorkOrderPriorityEnum
    assigned_to: str | None = None
    work_order_id: int | None = None
    confirmed_at: datetime | None = None
    confirmed_by: int | None = None
    cancelled_at: datetime | None = None
    cancelled_by: int | None = None
    created_at: datetime
    created_by: int | None = None

    model_config = ConfigDict(from_attributes=True)


class StageWorkOrderDayRequest(BaseModel):
    target_date: date
    factory_section_id: int | None = None
    factory_id: int | None = None


class ListWorkOrderSchedulesParams(BaseModel):
    factory_id: int | None = None
    machine_id: int | None = None
    start_date_from: date | None = None
    start_date_to: date | None = None
    status: WorkOrderScheduleStatusEnum | None = None
