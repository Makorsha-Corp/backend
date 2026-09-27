"""Project component item ledger schemas"""
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ProjectComponentItemLedgerBase(BaseModel):
    """Base project component item ledger schema"""
    project_component_id: int
    item_id: int
    transaction_type: str = Field(..., pattern=r'^(purchase_order|manual_add|transfer_in|transfer_out|consumption|damaged|inventory_adjustment|cost_adjustment)$')
    quantity: int = Field(..., ge=0)
    unit_cost: Decimal = Field(..., ge=0)
    total_cost: Decimal = Field(..., ge=0)

    # State tracking
    qty_before: int
    qty_after: int
    value_before: Decimal | None = None
    value_after: Decimal | None = None
    avg_price_before: Decimal | None = None
    avg_price_after: Decimal | None = None

    # Attribution
    source_type: str
    source_id: int | None = None
    order_id: int | None = None
    invoice_id: int | None = None

    # Transfer context
    transfer_source_type: str | None = None
    transfer_source_id: int | None = None
    transfer_destination_type: str | None = None
    transfer_destination_id: int | None = None

    # Notes
    notes: str | None = None


class ProjectComponentItemLedgerCreate(ProjectComponentItemLedgerBase):
    """Schema for creating a project component item ledger entry (workspace_id and performed_by injected by service)"""


class ProjectComponentItemLedgerUpdate(BaseModel):
    """Schema for updating a project component item ledger entry (generally should be immutable)"""
    notes: str | None = None


class ProjectComponentItemLedgerInDB(ProjectComponentItemLedgerBase):
    """Project component item ledger schema as stored in database"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    performed_by: int
    performed_at: datetime


class ProjectComponentItemLedgerResponse(ProjectComponentItemLedgerInDB):
    """Project component item ledger response schema"""
