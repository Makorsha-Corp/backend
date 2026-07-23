"""Work order template schemas"""
from datetime import date, datetime
from decimal import Decimal
from typing import List, Literal
from pydantic import BaseModel, ConfigDict
from app.models.enums import WorkOrderPriorityEnum
from app.schemas.work_order_item import WorkOrderItemActionType

WorkOrderTemplateGenerationMode = Literal['schedule', 'draft']


class WorkOrderTemplateItemCreate(BaseModel):
    item_id: int
    quantity: Decimal = Decimal("1")
    action_type: WorkOrderItemActionType = 'CONSUME'
    replaced_item_id: int | None = None
    notes: str | None = None


class WorkOrderTemplateItemUpdate(BaseModel):
    quantity: Decimal | None = None
    action_type: WorkOrderItemActionType | None = None
    replaced_item_id: int | None = None
    notes: str | None = None


class WorkOrderTemplateItemResponse(BaseModel):
    id: int
    workspace_id: int
    work_order_template_id: int
    item_id: int
    item_name: str | None = None
    quantity: Decimal
    action_type: WorkOrderItemActionType
    replaced_item_id: int | None = None
    replaced_item_name: str | None = None
    notes: str | None = None

    model_config = ConfigDict(from_attributes=True)


class WorkOrderTemplateCreate(BaseModel):
    template_name: str
    description: str | None = None
    work_order_type_id: int
    priority: WorkOrderPriorityEnum = WorkOrderPriorityEnum.MEDIUM
    assigned_to: str | None = None
    uses_inventory: bool = False
    account_id: int | None = None
    cost: Decimal | None = None
    requires_approval: bool = False
    notes: str | None = None
    items: List[WorkOrderTemplateItemCreate] | None = None
    approver_user_ids: List[int] | None = None
    is_recurring: bool = False
    recurrence_type: str | None = None
    recurrence_day: int | None = None
    next_generation_date: date | None = None
    auto_generate: bool = False
    generation_mode: WorkOrderTemplateGenerationMode = 'schedule'
    default_factory_section_id: int | None = None
    default_machine_id: int | None = None


class WorkOrderTemplateUpdate(BaseModel):
    template_name: str | None = None
    description: str | None = None
    work_order_type_id: int | None = None
    priority: WorkOrderPriorityEnum | None = None
    assigned_to: str | None = None
    uses_inventory: bool | None = None
    account_id: int | None = None
    cost: Decimal | None = None
    requires_approval: bool | None = None
    notes: str | None = None
    is_active: bool | None = None
    approver_user_ids: List[int] | None = None
    is_recurring: bool | None = None
    recurrence_type: str | None = None
    recurrence_day: int | None = None
    next_generation_date: date | None = None
    auto_generate: bool | None = None
    generation_mode: WorkOrderTemplateGenerationMode | None = None
    default_factory_section_id: int | None = None
    default_machine_id: int | None = None


class WorkOrderTemplateResponse(BaseModel):
    id: int
    workspace_id: int
    template_name: str
    description: str | None = None
    work_order_type_id: int
    work_order_type_name: str | None = None
    priority: WorkOrderPriorityEnum
    assigned_to: str | None = None
    uses_inventory: bool
    account_id: int | None = None
    cost: Decimal | None = None
    requires_approval: bool
    notes: str | None = None
    is_active: bool
    is_recurring: bool = False
    recurrence_type: str | None = None
    recurrence_day: int | None = None
    next_generation_date: date | None = None
    auto_generate: bool = False
    generation_mode: WorkOrderTemplateGenerationMode = 'schedule'
    default_factory_section_id: int | None = None
    default_machine_id: int | None = None
    created_by: int | None = None
    created_at: datetime
    updated_by: int | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class WorkOrderTemplateApproverCreate(BaseModel):
    user_id: int


class WorkOrderTemplateApproverResponse(BaseModel):
    id: int
    workspace_id: int
    work_order_template_id: int
    user_id: int
    user_name: str | None = None
    approver_slot: str | None = None

    model_config = ConfigDict(from_attributes=True)


class WorkOrderFromTemplateCreate(BaseModel):
    """Overrides when generating a work order from a template — machine is required
    since a template doesn't know which machine it'll be applied to."""
    machine_id: int
    title: str | None = None
    description: str | None = None
    assigned_to: str | None = None
    planned_date: date | None = None


class GenerateWorkOrderDraftsRequest(BaseModel):
    """Generate draft work orders from recurring templates for a given day."""
    target_date: date
    factory_section_id: int | None = None
    factory_id: int | None = None
