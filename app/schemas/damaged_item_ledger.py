"""Damaged item ledger schemas"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime
from decimal import Decimal


class DamagedItemLedgerBase(BaseModel):
    """Base damaged item ledger schema"""
    factory_id: int
    item_id: int
    transaction_type: str = Field(..., pattern=r'^(purchase_order|manual_add|transfer_in|transfer_out|consumption|damaged|inventory_adjustment|cost_adjustment)$')
    quantity: int = Field(..., ge=0)
    unit_cost: Decimal = Field(..., ge=0)
    total_cost: Decimal = Field(..., ge=0)

    # State tracking
    qty_before: int
    qty_after: int
    value_before: Optional[Decimal] = None
    value_after: Optional[Decimal] = None
    avg_price_before: Optional[Decimal] = None
    avg_price_after: Optional[Decimal] = None

    # Attribution
    source_type: str
    source_id: Optional[int] = None
    order_id: Optional[int] = None
    invoice_id: Optional[int] = None

    # Transfer context
    transfer_source_type: Optional[str] = None
    transfer_source_id: Optional[int] = None
    transfer_destination_type: Optional[str] = None
    transfer_destination_id: Optional[int] = None

    # Notes
    notes: Optional[str] = None


class DamagedItemLedgerCreate(DamagedItemLedgerBase):
    """Schema for creating a damaged item ledger entry (workspace_id and performed_by injected by service)"""
    pass


class DamagedItemLedgerUpdate(BaseModel):
    """Schema for updating a damaged item ledger entry (generally should be immutable)"""
    notes: Optional[str] = None


class DamagedItemLedgerInDB(DamagedItemLedgerBase):
    """Damaged item ledger schema as stored in database"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    performed_by: int
    performed_at: datetime


class DamagedItemLedgerResponse(DamagedItemLedgerInDB):
    """Damaged item ledger response schema"""
    pass
