"""Sales order schemas"""
from pydantic import BaseModel, ConfigDict
from datetime import datetime, date
from decimal import Decimal


class SalesOrderBase(BaseModel):
    """Base sales order schema"""
    account_id: int
    factory_id: int
    order_date: date
    quotation_sent_date: date | None = None
    expected_delivery_date: date | None = None
    notes: str | None = None


class SalesOrderCreate(SalesOrderBase):
    """Sales order creation schema - total_amount calculated from items"""
    total_amount: Decimal | None = None  # Calculated automatically if not provided
    current_status_id: int = 10  # Default to "Started" status


class SalesOrderUpdate(BaseModel):
    """Sales order update schema"""
    quotation_sent_date: date | None = None
    expected_delivery_date: date | None = None
    total_amount: Decimal | None = None
    current_status_id: int | None = None
    is_fully_delivered: bool | None = None
    invoice_id: int | None = None
    is_invoiced: bool | None = None
    notes: str | None = None


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
    created_by: int
    created_at: datetime
    updated_by: int | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class SalesOrderListResponse(SalesOrderResponse):
    """Sales order list response with related data"""
    customer_name: str | None = None
    factory_name: str | None = None
    current_status_name: str | None = None
    created_by_name: str | None = None

    model_config = ConfigDict(from_attributes=True)
