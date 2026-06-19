"""Expense order schemas"""
from datetime import date, datetime
from decimal import Decimal
from typing import List, Literal
from pydantic import BaseModel, ConfigDict


class ExpenseOrderItemCreate(BaseModel):
    description: str | None = None
    quantity: Decimal = 1
    unit: str | None = None
    unit_price: Decimal | None = None
    cost_center_type: str | None = None
    cost_center_id: int | None = None
    notes: str | None = None


class ExpenseOrderItemUpdate(BaseModel):
    description: str | None = None
    quantity: Decimal | None = None
    unit: str | None = None
    unit_price: Decimal | None = None
    cost_center_type: str | None = None
    cost_center_id: int | None = None
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
    cost_center_type: str | None = None
    cost_center_id: int | None = None
    approved: bool
    notes: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ExpenseOrderCreate(BaseModel):
    account_id: int | None = None
    expense_category: str
    expense_date: date | None = None
    due_date: date | None = None
    description: str | None = None
    expense_note: str | None = None
    internal_note: str | None = None
    current_status_id: int = 1
    order_workflow_id: int | None = None
    items: List[ExpenseOrderItemCreate] | None = None


ExpenseOrderSection = Literal['details', 'items', 'invoice']


class ExpenseOrderSectionConfirmRequest(BaseModel):
    section: ExpenseOrderSection
    confirmed: bool


class ExpenseOrderUpdate(BaseModel):
    account_id: int | None = None
    expense_category: str | None = None
    expense_date: date | None = None
    due_date: date | None = None
    current_status_id: int | None = None
    invoice_id: int | None = None
    required_approvals: int | None = None
    description: str | None = None
    expense_note: str | None = None
    internal_note: str | None = None
    details_confirmed: bool | None = None
    items_confirmed: bool | None = None
    invoice_confirmed: bool | None = None


class ExpenseOrderResponse(BaseModel):
    id: int
    workspace_id: int
    expense_number: str
    order_template_id: int | None = None
    account_id: int | None = None
    expense_category: str
    expense_date: date
    due_date: date | None = None
    subtotal: Decimal
    total_amount: Decimal
    current_status_id: int
    current_status_name: str | None = None
    order_workflow_id: int | None = None
    invoice_id: int | None = None
    required_approvals: int | None = None
    details_confirmed: bool = False
    items_confirmed: bool = False
    invoice_confirmed: bool = False
    description: str | None = None
    expense_note: str | None = None
    internal_note: str | None = None
    created_by: int
    created_at: datetime
    updated_by: int | None = None
    updated_at: datetime | None = None
    approved_by: int | None = None
    approved_at: datetime | None = None
    completed_by: int | None = None
    completed_at: datetime | None = None
    order_completed: bool = False

    model_config = ConfigDict(from_attributes=True)


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
    performer_name: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
