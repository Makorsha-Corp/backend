"""Sales delivery schemas"""
from pydantic import BaseModel, ConfigDict
from datetime import datetime, date


class SalesDeliveryBase(BaseModel):
    """Base sales delivery schema"""
    sales_order_id: int
    scheduled_date: date | None = None
    tracking_number: str | None = None
    notes: str | None = None


class SalesDeliveryCreate(SalesDeliveryBase):
    """Sales delivery creation schema"""
    delivery_status: str = 'planned'


class SalesDeliveryUpdate(BaseModel):
    """Sales delivery update schema"""
    scheduled_date: date | None = None
    actual_delivery_date: date | None = None
    delivery_status: str | None = None
    tracking_number: str | None = None
    notes: str | None = None


class SalesDeliveryResponse(SalesDeliveryBase):
    """Sales delivery response schema"""
    id: int
    workspace_id: int
    delivery_number: str
    actual_delivery_date: date | None = None
    delivery_status: str
    created_by: int
    created_at: datetime
    updated_by: int | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class SalesDeliveryListResponse(SalesDeliveryResponse):
    """Sales delivery list response with related data"""
    sales_order_number: str | None = None
    customer_name: str | None = None
    created_by_name: str | None = None

    model_config = ConfigDict(from_attributes=True)
