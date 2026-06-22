"""Schemas for item order history."""
from datetime import date, datetime
from decimal import Decimal
from typing import List, Literal

from pydantic import BaseModel, ConfigDict, Field


ItemOrderType = Literal['purchase_order', 'transfer_order', 'sales_order', 'work_order']


class ItemOrderRowResponse(BaseModel):
    order_type: ItemOrderType
    order_id: int
    order_number: str
    order_date: date | None = None
    quantity: Decimal
    unit_price: Decimal | None = None
    line_total: Decimal | None = None
    status_name: str | None = None
    account_name: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ItemOrdersListResponse(BaseModel):
    items: List[ItemOrderRowResponse] = Field(default_factory=list)
    total: int = 0
