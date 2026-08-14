"""Sales order schemas"""
from typing import List, Literal
from pydantic import BaseModel, ConfigDict
from datetime import datetime, date
from decimal import Decimal


class SalesOrderBase(BaseModel):
    """Base sales order schema"""
    account_id: int
    factory_id: int
    order_date: date
    expected_delivery_date: date | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    description: str | None = None


class SalesOrderCreate(SalesOrderBase):
    """Sales order creation schema - total_amount calculated from items"""
    total_amount: Decimal | None = None  # Calculated automatically if not provided
    current_status_id: int = 10  # Vestigial — retained at the DB level only, not used by the sales flow


class SalesOrderUpdate(BaseModel):
    """Sales order update schema"""
    expected_delivery_date: date | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    total_amount: Decimal | None = None
    is_fully_delivered: bool | None = None
    invoice_id: int | None = None
    is_invoiced: bool | None = None
    description: str | None = None
    required_approvals: int | None = None


class SalesOrderResponse(SalesOrderBase):
    """Sales order response schema"""
    id: int
    workspace_id: int
    sales_order_number: str
    total_amount: Decimal  # Calculated from items
    current_status_id: int
    is_fully_delivered: bool
    invoice_id: int | None = None
    is_invoiced: bool
    paid: bool
    invoice_payment_status: str | None = None  # Transient, attached from linked AccountInvoice

    # Approval workflow
    order_info_confirmed: bool
    items_confirmed: bool
    invoice_confirmed: bool
    required_approvals: int | None = None

    # Completion
    order_completed: bool
    completed_at: datetime | None = None

    created_by: int
    created_at: datetime
    updated_by: int | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class SalesOrderListResponse(SalesOrderResponse):
    """Sales order list response with related data"""
    customer_name: str | None = None
    factory_name: str | None = None
    created_by_name: str | None = None

    model_config = ConfigDict(from_attributes=True)


# ─── Approvers ────────────────────────────────────────────────

class SalesOrderApproverCreate(BaseModel):
    user_id: int


class SalesOrderApproverResponse(BaseModel):
    id: int
    workspace_id: int
    sales_order_id: int
    user_id: int
    user_name: str | None = None
    user_email: str | None = None
    user_position: str | None = None
    assigned_by: int | None = None
    assigned_at: datetime
    approved: bool
    approved_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class SalesOrderApprovalSummaryResponse(BaseModel):
    approved_count: int
    required: int
    met: bool


class SalesOrderApproversList(BaseModel):
    approvers: List[SalesOrderApproverResponse]
    summary: SalesOrderApprovalSummaryResponse


# ─── Section confirm ──────────────────────────────────────────

SalesOrderSection = Literal['order_info', 'items']


class SalesOrderSectionConfirmRequest(BaseModel):
    section: SalesOrderSection
    confirmed: bool


# ─── Events ───────────────────────────────────────────────────

class SalesOrderEventMetadata(BaseModel):
    user_id: int | None = None
    user_name: str | None = None
    invoice_id: int | None = None
    paid: bool | None = None
    delivery_id: int | None = None
    item_id: int | None = None
    tracking_number: str | None = None
    actual_delivery_date: str | None = None
    completion_code: str | None = None


class SalesOrderEventResponse(BaseModel):
    id: int
    workspace_id: int
    sales_order_id: int
    event_type: str
    description: str
    metadata: SalesOrderEventMetadata | None = None
    performed_by: int | None = None
    user_name: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
