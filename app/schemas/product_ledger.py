"""Product ledger schemas"""
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict


class ProductLedgerCreate(BaseModel):
    """Create product ledger entry (used internally by manager)"""
    factory_id: int
    item_id: int
    transaction_type: str
    quantity: int
    unit_cost: Decimal | None = None
    total_cost: Decimal | None = None
    qty_before: int
    qty_after: int
    avg_cost_before: Decimal | None = None
    avg_cost_after: Decimal | None = None
    source_type: str | None = None
    source_id: int | None = None
    transfer_source_type: str | None = None
    transfer_source_id: int | None = None
    transfer_destination_type: str | None = None
    transfer_destination_id: int | None = None
    notes: str | None = None


class ProductLedgerUpdate(BaseModel):
    """Update ledger entry - only notes can be updated (immutable)"""
    notes: str | None = None


class ProductLedgerResponse(BaseModel):
    """Product ledger response"""
    id: int
    workspace_id: int
    factory_id: int
    item_id: int
    transaction_type: str
    quantity: int
    unit_cost: Decimal | None = None
    total_cost: Decimal | None = None
    qty_before: int
    qty_after: int
    avg_cost_before: Decimal | None = None
    avg_cost_after: Decimal | None = None
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
