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
    expense_date: date | None = None
    due_date: date | None = None
    description: str | None = None
    expense_note: str | None = None
    internal_note: str | None = None
    current_status_id: int = 1
    order_workflow_id: int | None = None
    items: List[ExpenseOrderItemCreate] | None = None


class ExpenseOrderUpdate(BaseModel):
    account_id: int | None = None
    expense_category: str | None = None
    due_date: date | None = None
    current_status_id: int | None = None
    invoice_id: int | None = None
    description: str | None = None
    expense_note: str | None = None
    internal_note: str | None = None


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
    order_workflow_id: int | None = None
    invoice_id: int | None = None
    description: str | None = None
    expense_note: str | None = None
    internal_note: str | None = None
    created_by: int
    created_at: datetime
    updated_by: int | None = None
    updated_at: datetime | None = None
    approved_by: int | None = None
    approved_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
