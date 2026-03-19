"""Order part schemas"""
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from app.models.enums import UnstableTypeEnum


class OrderItemBase(BaseModel):
    """Base order item schema"""
    order_id: int
    part_id: int
    qty: int
    unit_cost: float | None = None
    note: str | None = None
    vendor_id: int | None = None
    brand: str | None = None
    office_note: str | None = None
    mrr_number: str | None = None


class OrderItemCreate(OrderItemBase):
    """Order item creation schema"""
    pass


class OrderItemUpdate(BaseModel):
    """Order item update schema"""
    qty: int | None = None
    unit_cost: float | None = None
    note: str | None = None
    vendor_id: int | None = None
    brand: str | None = None
    office_note: str | None = None
    mrr_number: str | None = None
    approved_pending_order: bool | None = None
    approved_office_order: bool | None = None
    approved_budget: bool | None = None
    approved_storage_withdrawal: bool | None = None
    in_storage: bool | None = None
    is_sample_sent_to_office: bool | None = None
    is_sample_received_by_office: bool | None = None
    unstable_type: UnstableTypeEnum | None = None


class OrderItemResponse(OrderItemBase):
    """Order part response schema"""
    id: int
    approved_pending_order: bool
    approved_office_order: bool
    approved_budget: bool
    approved_storage_withdrawal: bool
    in_storage: bool
    is_deleted: bool
    is_sample_sent_to_office: bool
    is_sample_received_by_office: bool
    part_sent_by_office_date: datetime | None
    part_received_by_factory_date: datetime | None
    part_purchased_date: datetime | None
    deleted_at: datetime | None
    qty_taken_from_storage: int
    unstable_type: UnstableTypeEnum | None

    model_config = ConfigDict(from_attributes=True)
