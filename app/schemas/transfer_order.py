"""Transfer order schemas"""
from datetime import datetime
from decimal import Decimal
from typing import List
from pydantic import BaseModel, ConfigDict


class TransferOrderItemCreate(BaseModel):
    item_id: int
    quantity: Decimal
    notes: str | None = None


class TransferOrderItemUpdate(BaseModel):
    quantity: Decimal | None = None
    approved: bool | None = None
    transferred_by: str | None = None
    transferred_at: datetime | None = None
    notes: str | None = None


class TransferOrderItemResponse(BaseModel):
    id: int
    workspace_id: int
    transfer_order_id: int
    line_number: int
    item_id: int
    item_name: str | None = None
    item_unit: str | None = None
    quantity: Decimal
    approved: bool
    approved_by: int | None = None
    approved_at: datetime | None = None
    transferred_by: str | None = None
    transferred_at: datetime | None = None
    notes: str | None = None

    model_config = ConfigDict(from_attributes=True)


class TransferOrderCreate(BaseModel):
    source_location_type: str
    source_location_id: int
    destination_location_type: str
    destination_location_id: int
    description: str | None = None
    current_status_id: int = 1
    items: List[TransferOrderItemCreate] | None = None


class TransferOrderUpdate(BaseModel):
    source_location_type: str | None = None
    source_location_id: int | None = None
    destination_location_type: str | None = None
    destination_location_id: int | None = None
    current_status_id: int | None = None
    required_approvals: int | None = None
    description: str | None = None


class TransferOrderResponse(BaseModel):
    id: int
    workspace_id: int
    transfer_number: str
    source_location_type: str
    source_location_id: int
    destination_location_type: str
    destination_location_id: int
    current_status_id: int
    current_status_name: str | None = None
    required_approvals: int | None = None
    description: str | None = None
    order_completed: bool = False
    created_by: int
    created_at: datetime
    updated_by: int | None = None
    updated_at: datetime | None = None
    completed_by: int | None = None
    completed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class TransferOrderApproverCreate(BaseModel):
    user_id: int


class TransferOrderApproverResponse(BaseModel):
    id: int
    workspace_id: int
    transfer_order_id: int
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


class TransferOrderApproversList(BaseModel):
    approvers: List[TransferOrderApproverResponse]
    summary: ApprovalSummaryResponse


class TransferOrderEventChange(BaseModel):
    field: str
    label: str
    from_value: str | None = None
    to_value: str | None = None


class TransferOrderEventMetadata(BaseModel):
    changes: list[TransferOrderEventChange] | None = None
    user_id: int | None = None
    user_name: str | None = None
    lines_posted: int | None = None


class TransferOrderEventResponse(BaseModel):
    id: int
    workspace_id: int
    transfer_order_id: int
    event_type: str
    description: str
    metadata: TransferOrderEventMetadata | None = None
    performed_by: int | None = None
    user_name: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
