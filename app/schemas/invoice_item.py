"""Invoice item schemas"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime
from decimal import Decimal


class InvoiceItemBase(BaseModel):
    description: str
    item_id: Optional[int] = None
    source_order_item_id: Optional[int] = None
    source_order_item_type: Optional[str] = Field(None, max_length=30)
    quantity: Decimal = Field(..., gt=0)
    unit: Optional[str] = Field(None, max_length=50)
    unit_price: Decimal = Field(..., ge=0)
    line_subtotal: Decimal = Field(..., ge=0)
    line_number: int = 1


class InvoiceItemCreate(InvoiceItemBase):
    invoice_id: int


class InvoiceItemUpdate(BaseModel):
    description: Optional[str] = None
    quantity: Optional[Decimal] = Field(None, gt=0)
    unit: Optional[str] = Field(None, max_length=50)
    unit_price: Optional[Decimal] = Field(None, ge=0)
    line_subtotal: Optional[Decimal] = Field(None, ge=0)
    line_number: Optional[int] = None


class InvoiceItemResponse(InvoiceItemBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    invoice_id: int
    last_synced_at: Optional[datetime] = None
    created_at: datetime
    created_by: Optional[int] = None
