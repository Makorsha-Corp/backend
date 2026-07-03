"""Expense order schemas"""
from datetime import date, datetime
from decimal import Decimal
from typing import List
from pydantic import BaseModel, ConfigDict


class ExpenseOrderItemCreate(BaseModel):
    description: str | None = None
    quantity: Decimal = 1
    unit: str | None = None
    unit_price: Decimal | None = None
    notes: str | None = None


class ExpenseOrderItemUpdate(BaseModel):
    description: str | None = None
    quantity: Decimal | None = None
    unit: str | None = None
    unit_price: Decimal | None = None
    approved: bool | None = None
    notes: str | None = None


class ExpenseOrderItemResponse(BaseModel):
    id: int
    workspace_id: int
    expense_order_id: int
    line_number: int
    description: str | None = None
    quantity: Decimal
    unit: str | None = None
    unit_price: Decimal | None = None
    line_subtotal: Decimal | None = None
    approved: bool
    notes: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ExpenseOrderCreate(BaseModel):
    account_id: int | None = None
    expense_category: str
    cost_center_id: int | None = None
    expense_date: date | None = None
    due_date: date | None = None
    description: str | None = None
    order_template_id: int | None = None
    items: List[ExpenseOrderItemCreate] | None = None


class ExpenseOrderFromTemplateCreate(BaseModel):
    expense_date: date | None = None
    due_date: date | None = None
    description: str | None = None


class ExpenseOrderUpdate(BaseModel):
    account_id: int | None = None
    expense_category: str | None = None
    cost_center_id: int | None = None
    expense_date: date | None = None
    due_date: date | None = None
    invoice_id: int | None = None
    required_approvals: int | None = None
    description: str | None = None


class ExpenseOrderResponse(BaseModel):
    id: int
    workspace_id: int
    expense_number: str
    order_template_id: int | None = None
    account_id: int | None = None
    expense_category: str
    cost_center_id: int | None = None
    expense_date: date
    due_date: date | None = None
    subtotal: Decimal
    total_amount: Decimal
    invoice_id: int | None = None
    required_approvals: int | None = None
    description: str | None = None
    created_by: int
    created_at: datetime
    updated_by: int | None = None
    updated_at: datetime | None = None
    items_updated_at: datetime | None = None
    approved_by: int | None = None
    approved_at: datetime | None = None
    completed_by: int | None = None
    completed_at: datetime | None = None
    order_completed: bool = False
    voided: bool = False
    void_note: str | None = None
    voided_at: datetime | None = None
    voided_by: int | None = None

    model_config = ConfigDict(from_attributes=True)


class ExpenseOrderVoidRequest(BaseModel):
    void_note: str


class ExpenseOrderApproverCreate(BaseModel):
    user_id: int


class ExpenseOrderApproverResponse(BaseModel):
    id: int
    workspace_id: int
    expense_order_id: int
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


class ExpenseOrderApproversList(BaseModel):
    approvers: List[ExpenseOrderApproverResponse]
    summary: ApprovalSummaryResponse


class ExpenseOrderEventMetadata(BaseModel):
    changes: List[dict] | None = None
    user_id: int | None = None
    user_name: str | None = None
    line_number: int | None = None
    invoice_id: int | None = None


class ExpenseOrderEventResponse(BaseModel):
    id: int
    workspace_id: int
    expense_order_id: int
    event_type: str
    description: str
    metadata: ExpenseOrderEventMetadata | dict | None = None
    performed_by: int | None = None
    user_name: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
