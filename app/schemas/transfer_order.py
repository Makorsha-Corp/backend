"""Transfer order schemas"""
from datetime import date, datetime
from decimal import Decimal
from typing import List
from pydantic import BaseModel, ConfigDict


class TransferOrderItemCreate(BaseModel):
    item_id: int
    quantity: Decimal
    notes: str | None = None


class TransferOrderItemUpdate(BaseModel):
    quantity: Decimal | None = None
    approved: bool | None = None
    transferred_by: str | None = None
    transferred_at: datetime | None = None
    notes: str | None = None


class TransferOrderItemResponse(BaseModel):
    id: int
    workspace_id: int
    transfer_order_id: int
    line_number: int
    item_id: int
    item_name: str | None = None
    item_unit: str | None = None
    quantity: Decimal
    approved: bool
    approved_by: int | None = None
    approved_at: datetime | None = None
    transferred_by: str | None = None
    transferred_at: datetime | None = None
    notes: str | None = None

    model_config = ConfigDict(from_attributes=True)


class TransferOrderCreate(BaseModel):
    source_location_type: str
    source_location_id: int
    destination_location_type: str
    destination_location_id: int
    order_date: date | None = None
    description: str | None = None
    note: str | None = None
    current_status_id: int = 1
    items: List[TransferOrderItemCreate] | None = None


class TransferOrderUpdate(BaseModel):
    current_status_id: int | None = None
    description: str | None = None
    note: str | None = None


class TransferOrderResponse(BaseModel):
    id: int
    workspace_id: int
    transfer_number: str
    source_location_type: str
    source_location_id: int
    destination_location_type: str
    destination_location_id: int
    order_date: date
    current_status_id: int
    description: str | None = None
    note: str | None = None
    created_by: int
    created_at: datetime
    updated_by: int | None = None
    updated_at: datetime | None = None
    completed_by: int | None = None
    completed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)
