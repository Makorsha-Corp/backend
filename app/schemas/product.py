"""Product schemas (finished goods)"""
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict


class ProductCreate(BaseModel):
    """Create product record"""
    item_id: int
    factory_id: int
    qty: int = 0
    avg_cost: Decimal | None = None
    selling_price: Decimal | None = None
    min_order_qty: int | None = None
    is_available_for_sale: bool = False
    note: str | None = None


class ProductUpdate(BaseModel):
    """Update product record"""
    qty: int | None = None
    avg_cost: Decimal | None = None
    selling_price: Decimal | None = None
    min_order_qty: int | None = None
    is_available_for_sale: bool | None = None
    note: str | None = None


class ProductResponse(BaseModel):
    """Product response"""
    id: int
    workspace_id: int
    item_id: int
    item_name: str | None = None
    item_unit: str | None = None
    factory_id: int
    qty: int
    avg_cost: Decimal | None = None
    selling_price: Decimal | None = None
    min_order_qty: int | None = None
    is_available_for_sale: bool
    note: str | None = None

    created_at: datetime
    created_by: int | None = None
    updated_at: datetime | None = None
    updated_by: int | None = None

    is_active: bool
    is_deleted: bool
    deleted_at: datetime | None = None
    deleted_by: int | None = None

    model_config = ConfigDict(from_attributes=True)
