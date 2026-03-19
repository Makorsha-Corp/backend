"""Work order schemas"""
from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict
from app.models.enums import WorkTypeEnum, WorkOrderPriorityEnum, WorkOrderStatusEnum


class WorkOrderCreate(BaseModel):
    """Create work order"""
    work_type: WorkTypeEnum
    title: str
    description: str | None = None
    priority: WorkOrderPriorityEnum = WorkOrderPriorityEnum.MEDIUM
    factory_id: int
    machine_id: int | None = None
    project_component_id: int | None = None
    start_date: date | None = None
    end_date: date | None = None
    cost: Decimal | None = None
    assigned_to: str | None = None
    notes: str | None = None


class WorkOrderUpdate(BaseModel):
    """Update work order"""
    work_type: WorkTypeEnum | None = None
    title: str | None = None
    description: str | None = None
    priority: WorkOrderPriorityEnum | None = None
    status: WorkOrderStatusEnum | None = None
    machine_id: int | None = None
    project_component_id: int | None = None
    start_date: date | None = None
    end_date: date | None = None
    cost: Decimal | None = None
    assigned_to: str | None = None
    order_approved: bool | None = None
    cost_approved: bool | None = None
    notes: str | None = None
    completion_notes: str | None = None


class WorkOrderResponse(BaseModel):
    """Work order response"""
    id: int
    workspace_id: int
    work_order_number: str
    work_type: WorkTypeEnum
    title: str
    description: str | None = None
    priority: WorkOrderPriorityEnum
    status: WorkOrderStatusEnum
    factory_id: int
    machine_id: int | None = None
    project_component_id: int | None = None
    start_date: date | None = None
    end_date: date | None = None
    cost: Decimal | None = None
    assigned_to: str | None = None

    order_approved: bool
    order_approved_by: int | None = None
    order_approved_at: datetime | None = None
    cost_approved: bool
    cost_approved_by: int | None = None
    cost_approved_at: datetime | None = None

    notes: str | None = None
    completion_notes: str | None = None

    created_at: datetime
    created_by: int | None = None
    updated_at: datetime | None = None
    updated_by: int | None = None

    is_active: bool
    is_deleted: bool
    deleted_at: datetime | None = None
    deleted_by: int | None = None

    model_config = ConfigDict(from_attributes=True)
