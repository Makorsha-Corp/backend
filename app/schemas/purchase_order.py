"""Purchase order schemas"""
from datetime import datetime
from decimal import Decimal
from typing import List, Literal
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
    account_id: int
    destination_type: str
    destination_id: int
    description: str | None = None
    order_note: str | None = None
    internal_note: str | None = None
    current_status_id: int = 1
    order_workflow_id: int | None = None
    items: List[PurchaseOrderItemCreate] | None = None


class PurchaseOrderUpdate(BaseModel):
    account_id: int | None = None
    current_status_id: int | None = None
    invoice_id: int | None = None
    description: str | None = None
    order_note: str | None = None
    internal_note: str | None = None


class PurchaseOrderResponse(BaseModel):
    id: int
    workspace_id: int
    po_number: str
    account_id: int
    destination_type: str
    destination_id: int
    subtotal: Decimal
    total_amount: Decimal
    current_status_id: int
    order_workflow_id: int | None = None
    invoice_id: int | None = None
    description: str | None = None
    order_note: str | None = None
    internal_note: str | None = None
    created_by: int
    created_at: datetime
    updated_by: int | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
