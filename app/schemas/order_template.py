"""Order template schemas - reusable expense order templates"""
from datetime import date, datetime
from decimal import Decimal
from typing import List
from pydantic import BaseModel, ConfigDict


class OrderTemplateItemCreate(BaseModel):
    description: str | None = None
    quantity: Decimal = 1
    unit: str | None = None
    unit_price: Decimal | None = None
    notes: str | None = None


class OrderTemplateItemUpdate(BaseModel):
    description: str | None = None
    quantity: Decimal | None = None
    unit: str | None = None
    unit_price: Decimal | None = None
    notes: str | None = None


class OrderTemplateItemResponse(BaseModel):
    id: int
    workspace_id: int
    order_template_id: int
    line_number: int
    description: str | None = None
    quantity: Decimal
    unit: str | None = None
    unit_price: Decimal | None = None
    line_subtotal: Decimal | None = None
    notes: str | None = None

    model_config = ConfigDict(from_attributes=True)


class OrderTemplateCreate(BaseModel):
    template_name: str
    description: str | None = None
    account_id: int | None = None
    expense_category: str | None = None
    is_recurring: bool = False
    recurrence_type: str | None = None
    recurrence_interval: int | None = None
    recurrence_day: int | None = None
    start_date: date | None = None
    end_date: date | None = None
    generate_days_before: int = 0
    auto_approve: bool = False
    requires_approval: bool = True
    default_approver_id: int | None = None
    notes: str | None = None
    items: List[OrderTemplateItemCreate] | None = None


class OrderTemplateUpdate(BaseModel):
    template_name: str | None = None
    description: str | None = None
    account_id: int | None = None
    expense_category: str | None = None
    is_recurring: bool | None = None
    recurrence_type: str | None = None
    recurrence_interval: int | None = None
    recurrence_day: int | None = None
    start_date: date | None = None
    end_date: date | None = None
    next_generation_date: date | None = None
    is_active: bool | None = None
    auto_approve: bool | None = None
    requires_approval: bool | None = None
    default_approver_id: int | None = None
    notes: str | None = None


class OrderTemplateResponse(BaseModel):
    id: int
    workspace_id: int
    template_name: str
    description: str | None = None
    account_id: int | None = None
    expense_category: str | None = None
    is_recurring: bool
    recurrence_type: str | None = None
    recurrence_interval: int | None = None
    recurrence_day: int | None = None
    start_date: date | None = None
    end_date: date | None = None
    next_generation_date: date | None = None
    last_generated_date: date | None = None
    is_active: bool
    generate_days_before: int
    auto_approve: bool
    requires_approval: bool
    default_approver_id: int | None = None
    notes: str | None = None
    created_by: int | None = None
    created_at: datetime
    updated_by: int | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
