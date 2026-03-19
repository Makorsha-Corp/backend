"""Unified inventory schemas (STORAGE, DAMAGED, WASTE, SCRAP)"""
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict
from app.models.enums import InventoryTypeEnum


class InventoryCreate(BaseModel):
    """Create inventory record"""
    item_id: int
    inventory_type: InventoryTypeEnum
    factory_id: int
    qty: int = 0
    avg_price: Decimal | None = None
    note: str | None = None


class InventoryUpdate(BaseModel):
    """Update inventory record"""
    qty: int | None = None
    avg_price: Decimal | None = None
    note: str | None = None


class InventoryResponse(BaseModel):
    """Inventory response"""
    id: int
    workspace_id: int
    item_id: int
    item_name: str | None = None
    item_unit: str | None = None
    inventory_type: InventoryTypeEnum
    factory_id: int
    qty: int
    avg_price: Decimal | None = None
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
