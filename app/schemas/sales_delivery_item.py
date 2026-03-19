"""Sales delivery item schemas"""
from pydantic import BaseModel, ConfigDict


class SalesDeliveryItemInput(BaseModel):
    """Simple input schema for creating delivery items (used with delivery creation)"""
    sales_order_item_id: int
    quantity_delivered: int
    notes: str | None = None


class SalesDeliveryItemBase(BaseModel):
    """Base sales delivery item schema"""
    sales_order_item_id: int
    item_id: int
    quantity_delivered: int
    notes: str | None = None


class SalesDeliveryItemCreate(SalesDeliveryItemBase):
    """Sales delivery item creation schema"""
    delivery_id: int
    workspace_id: int


class SalesDeliveryItemUpdate(BaseModel):
    """Sales delivery item update schema"""
    quantity_delivered: int | None = None
    notes: str | None = None


class SalesDeliveryItemResponse(SalesDeliveryItemBase):
    """Sales delivery item response schema"""
    id: int
    workspace_id: int
    delivery_id: int

    model_config = ConfigDict(from_attributes=True)


class SalesDeliveryItemListResponse(SalesDeliveryItemResponse):
    """Sales delivery item list response with related data"""
    item_name: str | None = None
    delivery_number: str | None = None

    model_config = ConfigDict(from_attributes=True)
