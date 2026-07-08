"""Work order schemas"""
from datetime import date, datetime
from decimal import Decimal
from typing import List, Literal
from pydantic import BaseModel, ConfigDict
from app.models.enums import WorkOrderPriorityEnum, WorkOrderStatusEnum


class WorkOrderCreate(BaseModel):
    """Create work order"""
    work_order_type_id: int
    title: str
    description: str | None = None
    priority: WorkOrderPriorityEnum = WorkOrderPriorityEnum.MEDIUM
    factory_id: int
    machine_id: int | None = None
    project_component_id: int | None = None
    start_date: date | None = None
    end_date: date | None = None
    # Decided once at creation — whether this order will ever consume stock items.
    uses_inventory: bool = True
    cost: Decimal | None = None
    account_id: int | None = None
    assigned_to: str | None = None


class WorkOrderUpdate(BaseModel):
    """Update work order"""
    work_order_type_id: int | None = None
    title: str | None = None
    description: str | None = None
    priority: WorkOrderPriorityEnum | None = None
    machine_id: int | None = None
    project_component_id: int | None = None
    start_date: date | None = None
    end_date: date | None = None
    cost: Decimal | None = None
    account_id: int | None = None
    assigned_to: str | None = None
    required_approvals: int | None = None
    completion_notes: str | None = None


class WorkOrderResponse(BaseModel):
    """Work order response"""
    id: int
    workspace_id: int
    work_order_number: str
    work_order_type_id: int
    work_order_type_name: str | None = None
    title: str
    description: str | None = None
    priority: WorkOrderPriorityEnum
    status: WorkOrderStatusEnum
    factory_id: int
    machine_id: int | None = None
    project_component_id: int | None = None
    start_date: date | None = None
    end_date: date | None = None
    uses_inventory: bool
    cost: Decimal | None = None
    account_id: int | None = None
    invoice_id: int | None = None
    assigned_to: str | None = None

    required_approvals: int | None = None
    approved_by: int | None = None
    approved_at: datetime | None = None

    started_by: int | None = None
    started_at: datetime | None = None
    completed_by: int | None = None
    completed_at: datetime | None = None

    void_note: str | None = None
    voided_at: datetime | None = None
    voided_by: int | None = None

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


class WorkOrderVoidRequest(BaseModel):
    void_note: str


class WorkOrderCompleteRequest(BaseModel):
    completion_notes: str | None = None
    # When the order targets a machine, the caller should explicitly choose what state
    # to leave it in — if omitted, falls back to whatever status it had before starting.
    machine_status: Literal['IDLE', 'RUNNING'] | None = None


class WorkOrderApproverCreate(BaseModel):
    user_id: int


class WorkOrderApproverResponse(BaseModel):
    id: int
    workspace_id: int
    work_order_id: int
    user_id: int
    user_name: str | None = None
    user_email: str | None = None
    user_position: str | None = None
    assigned_by: int | None = None
    assigned_at: datetime
    approved: bool
    approved_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ApprovalSummaryResponse(BaseModel):
    approved_count: int
    required: int
    met: bool


class WorkOrderApproversList(BaseModel):
    approvers: List[WorkOrderApproverResponse]
    summary: ApprovalSummaryResponse


class WorkOrderEventMetadata(BaseModel):
    changes: List[dict] | None = None
    user_id: int | None = None
    user_name: str | None = None
    item_id: int | None = None
    item_name: str | None = None
    invoice_id: int | None = None
    void_note: str | None = None


class WorkOrderEventResponse(BaseModel):
    id: int
    workspace_id: int
    work_order_id: int
    event_type: str
    description: str
    metadata: WorkOrderEventMetadata | dict | None = None
    performed_by: int | None = None
    user_name: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
