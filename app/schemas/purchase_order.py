"""Purchase order schemas"""
from datetime import date, datetime
from decimal import Decimal
from typing import List, Literal

PurchaseOrderSection = Literal['supplier', 'details', 'notes', 'items', 'invoice']
from pydantic import BaseModel, ConfigDict


class ActiveOrderRow(BaseModel):
    """Unified row for purchase + transfer orders in context (machine / storage / project)."""

    order_kind: Literal["purchase", "transfer"]
    id: int
    number: str
    summary: str | None = None
    current_status_id: int
    status_name: str | None = None
    created_at: datetime
    total_amount: Decimal | None = None

    model_config = ConfigDict(from_attributes=True)


class PurchaseOrderItemCreate(BaseModel):
    item_id: int
    quantity_ordered: Decimal
    unit_price: Decimal
    notes: str | None = None


class PurchaseOrderItemUpdate(BaseModel):
    quantity_ordered: Decimal | None = None
    quantity_received: Decimal | None = None
    unit_price: Decimal | None = None
    notes: str | None = None


class PurchaseOrderItemResponse(BaseModel):
    id: int
    workspace_id: int
    purchase_order_id: int
    line_number: int
    item_id: int
    item_name: str | None = None
    item_unit: str | None = None
    quantity_ordered: Decimal
    quantity_received: Decimal
    unit_price: Decimal
    line_subtotal: Decimal
    notes: str | None = None

    model_config = ConfigDict(from_attributes=True)


class PurchaseOrderCreate(BaseModel):
    account_id: int | None = None
    destination_type: str
    destination_id: int
    order_date: date | None = None
    expected_delivery_date: date | None = None
    description: str | None = None
    order_note: str | None = None
    current_status_id: int = 1
    order_workflow_id: int | None = None
    required_approvals: int | None = None
    items: List[PurchaseOrderItemCreate] | None = None


class PurchaseOrderSectionConfirmRequest(BaseModel):
    section: PurchaseOrderSection
    confirmed: bool


class PurchaseOrderUpdate(BaseModel):
    account_id: int | None = None
    destination_type: str | None = None
    destination_id: int | None = None
    order_date: date | None = None
    expected_delivery_date: date | None = None
    current_status_id: int | None = None
    invoice_id: int | None = None
    required_approvals: int | None = None
    description: str | None = None
    order_note: str | None = None
    supplier_confirmed: bool | None = None
    details_confirmed: bool | None = None
    notes_confirmed: bool | None = None
    items_confirmed: bool | None = None
    invoice_confirmed: bool | None = None


class PurchaseOrderResponse(BaseModel):
    id: int
    workspace_id: int
    po_number: str
    account_id: int | None = None
    destination_type: str
    destination_id: int
    order_date: date | None = None
    expected_delivery_date: date | None = None
    actual_delivery_date: date | None = None
    subtotal: Decimal
    total_amount: Decimal
    current_status_id: int
    order_workflow_id: int | None = None
    invoice_id: int | None = None
    required_approvals: int | None = None
    description: str | None = None
    order_note: str | None = None
    supplier_confirmed: bool = False
    details_confirmed: bool = False
    notes_confirmed: bool = False
    items_confirmed: bool = False
    invoice_confirmed: bool = False
    created_by: int
    created_at: datetime
    updated_by: int | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class PurchaseOrderApproverCreate(BaseModel):
    user_id: int


class PurchaseOrderApproverResponse(BaseModel):
    id: int
    workspace_id: int
    purchase_order_id: int
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


class PurchaseOrderApproversList(BaseModel):
    approvers: List[PurchaseOrderApproverResponse]
    summary: ApprovalSummaryResponse


class PurchaseOrderEventChange(BaseModel):
    field: str
    label: str
    from_value: str | None = None
    to_value: str | None = None


class PurchaseOrderEventMetadata(BaseModel):
    changes: list[PurchaseOrderEventChange] | None = None
    item_id: int | None = None
    item_name: str | None = None
    line_number: int | None = None
    quantity_ordered: str | None = None
    unit_price: str | None = None
    user_id: int | None = None
    user_name: str | None = None


class PurchaseOrderEventResponse(BaseModel):
    id: int
    workspace_id: int
    purchase_order_id: int
    event_type: str
    description: str
    metadata: PurchaseOrderEventMetadata | None = None
    performed_by: int | None = None
    user_name: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
