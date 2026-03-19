"""Sales order item schemas"""
from pydantic import BaseModel, ConfigDict
from decimal import Decimal


class SalesOrderItemInput(BaseModel):
    """Simple input schema for creating order items (used with order creation)"""
    item_id: int
    quantity_ordered: int
    unit_price: Decimal
    notes: str | None = None


class SalesOrderItemBase(BaseModel):
    """Base sales order item schema"""
    item_id: int
    quantity_ordered: int
    unit_price: Decimal
    line_total: Decimal
    notes: str | None = None


class SalesOrderItemCreate(SalesOrderItemBase):
    """Sales order item creation schema (for direct item creation)"""
    sales_order_id: int
    workspace_id: int


class SalesOrderItemUpdate(BaseModel):
    """Sales order item update schema"""
    quantity_ordered: int | None = None
    quantity_delivered: int | None = None
    unit_price: Decimal | None = None
    line_total: Decimal | None = None
    notes: str | None = None


class SalesOrderItemResponse(SalesOrderItemBase):
    """Sales order item response schema"""
    id: int
    workspace_id: int
    sales_order_id: int
    quantity_delivered: int

    model_config = ConfigDict(from_attributes=True)


class SalesOrderItemListResponse(SalesOrderItemResponse):
    """Sales order item list response with related data"""
    item_name: str | None = None
    item_unit: str | None = None
    quantity_remaining: int | None = None

    model_config = ConfigDict(from_attributes=True)
