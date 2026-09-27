"""Invoice item schemas"""
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class InvoiceItemBase(BaseModel):
    description: str
    item_id: int | None = None
    source_order_item_id: int | None = None
    source_order_item_type: str | None = Field(None, max_length=30)
    quantity: Decimal = Field(..., gt=0)
    unit: str | None = Field(None, max_length=50)
    unit_price: Decimal = Field(..., ge=0)
    line_subtotal: Decimal = Field(..., ge=0)
    line_number: int = 1


class InvoiceItemCreate(InvoiceItemBase):
    invoice_id: int


class InvoiceItemUpdate(BaseModel):
    description: str | None = None
    quantity: Decimal | None = Field(None, gt=0)
    unit: str | None = Field(None, max_length=50)
    unit_price: Decimal | None = Field(None, ge=0)
    line_subtotal: Decimal | None = Field(None, ge=0)
    line_number: int | None = None


class InvoiceItemResponse(InvoiceItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    invoice_id: int
    last_synced_at: datetime | None = None
    created_at: datetime
    created_by: int | None = None
