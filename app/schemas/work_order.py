"""Work order schemas"""
from datetime import date, datetime
from decimal import Decimal
from typing import List, Literal, TYPE_CHECKING
from pydantic import BaseModel, ConfigDict, computed_field
from app.models.enums import WorkOrderPriorityEnum, WorkOrderStatusEnum

if TYPE_CHECKING:
    from app.schemas.work_order_item import WorkOrderItemResponse


class WorkOrderCreate(BaseModel):
    """Create work order"""
    work_order_type_id: int
    title: str
    description: str | None = None
    priority: WorkOrderPriorityEnum = WorkOrderPriorityEnum.MEDIUM
    factory_id: int
    machine_id: int | None = None
    project_component_id: int | None = None
    planned_date: date | None = None
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
    planned_date: date | None = None
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
    planned_date: date | None = None
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

    work_order_template_id: int | None = None

    created_at: datetime
    created_by: int | None = None
    updated_at: datetime | None = None
    updated_by: int | None = None

    is_active: bool
    is_deleted: bool
    deleted_at: datetime | None = None
    deleted_by: int | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def calendar_date(self) -> date:
        """Planned planned_date, or created_at day when unscheduled (drafts)."""
        if self.planned_date is not None:
            return self.planned_date
        return self.created_at.date()

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
    approver_slot: str | None = None  # manager | agm


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
    approver_slot: str | None = None
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


class WorkOrderSheetItemLine(BaseModel):
    item_id: int
    quantity: Decimal
    action_type: Literal['CONSUME', 'INSTALL', 'REPLACE', 'BORROW'] = 'CONSUME'
    source_location_type: str | None = 'storage'
    source_location_id: int | None = None
    replaced_item_id: int | None = None


class WorkOrderSheetApproverLine(BaseModel):
    user_id: int
    approver_slot: str | None = None  # manager | agm


class WorkOrderSheetEntryCreate(BaseModel):
    """Single-transaction sheet row create — merges into existing WO when same machine+date+type."""
    machine_id: int
    work_order_type_id: int
    planned_date: date
    assigned_to: str | None = None
    description: str | None = None
    priority: WorkOrderPriorityEnum = WorkOrderPriorityEnum.MEDIUM
    account_id: int | None = None
    cost: Decimal | None = None
    template_id: int | None = None
    items: List[WorkOrderSheetItemLine] = []
    approvers: List[WorkOrderSheetApproverLine] = []


class WorkOrderSheetBundle(BaseModel):
    """Work order with embedded items + approvers for sheet view."""
    order: WorkOrderResponse
    items: List['WorkOrderItemResponse']
    approvers: WorkOrderApproversList


class WorkOrderSheetDailyCountsResponse(BaseModel):
    """Work-order counts keyed by calendar date ISO string (for calendar dots)."""
    counts: dict[str, int]


def _rebuild_work_order_sheet_bundle() -> None:
    from app.schemas.work_order_item import WorkOrderItemResponse
    WorkOrderSheetBundle.model_rebuild(_types_namespace={'WorkOrderItemResponse': WorkOrderItemResponse})


_rebuild_work_order_sheet_bundle()
