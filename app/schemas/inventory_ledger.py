"""Unified inventory ledger schemas"""
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict
from app.models.enums import InventoryTypeEnum


class InventoryLedgerCreate(BaseModel):
    """Create inventory ledger entry (used internally by manager)"""
    inventory_type: InventoryTypeEnum
    factory_id: int
    item_id: int
    transaction_type: str
    quantity: int
    unit_cost: Decimal | None = None
    total_cost: Decimal | None = None
    qty_before: int
    qty_after: int
    avg_price_before: Decimal | None = None
    avg_price_after: Decimal | None = None
    source_type: str | None = None
    source_id: int | None = None
    transfer_source_type: str | None = None
    transfer_source_id: int | None = None
    transfer_destination_type: str | None = None
    transfer_destination_id: int | None = None
    notes: str | None = None


class InventoryLedgerUpdate(BaseModel):
    """Update ledger entry - only notes can be updated (immutable)"""
    notes: str | None = None


class InventoryLedgerResponse(BaseModel):
    """Inventory ledger response"""
    id: int
    workspace_id: int
    inventory_type: InventoryTypeEnum
    factory_id: int
    item_id: int
    transaction_type: str
    quantity: int
    unit_cost: Decimal | None = None
    total_cost: Decimal | None = None
    qty_before: int
    qty_after: int
    avg_price_before: Decimal | None = None
    avg_price_after: Decimal | None = None
    source_type: str | None = None
    source_id: int | None = None
    transfer_source_type: str | None = None
    transfer_source_id: int | None = None
    transfer_destination_type: str | None = None
    transfer_destination_id: int | None = None
    notes: str | None = None
    performed_by: int | None = None
    performed_at: datetime

    model_config = ConfigDict(from_attributes=True)
