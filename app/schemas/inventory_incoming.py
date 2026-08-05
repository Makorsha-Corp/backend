"""Schemas for storage incoming order summaries (PO + inbound transfer)."""
from decimal import Decimal
from typing import List, Literal

from pydantic import BaseModel, ConfigDict, Field


class IncomingOrderLine(BaseModel):
    order_kind: Literal["purchase", "transfer"]
    order_id: int
    order_number: str
    status_name: str | None = None
    pending_qty: Decimal = Field(..., description="Unreceived PO qty or full transfer line qty")

    model_config = ConfigDict(from_attributes=True)


class ItemIncomingSummary(BaseModel):
    factory_id: int
    item_id: int
    total_pending_qty: Decimal
    order_count: int
    orders: List[IncomingOrderLine] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
