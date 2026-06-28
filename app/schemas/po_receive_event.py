from datetime import datetime
from decimal import Decimal
from typing import List, Literal
from pydantic import BaseModel, ConfigDict, model_validator


class PoReceiveEventItemCreate(BaseModel):
    po_item_id: int
    quantity_delta: Decimal


class PoReceiveEventCreate(BaseModel):
    event_type: Literal['receive', 'correction']
    rcc: str | None = None
    received_by: str | None = None
    correction_note: str | None = None
    items: List[PoReceiveEventItemCreate]

    @model_validator(mode='after')
    def validate_event(self) -> 'PoReceiveEventCreate':
        if not self.items:
            raise ValueError('At least one item must have a quantity delta')
        if self.event_type == 'correction' and not (self.correction_note or '').strip():
            raise ValueError('correction_note is required for correction events')
        if self.event_type == 'receive':
            for item in self.items:
                if item.quantity_delta <= 0:
                    raise ValueError('All quantity deltas must be positive for a receive event')
        return self


class PoReceiveEventItemResponse(BaseModel):
    id: int
    receive_event_id: int
    po_item_id: int
    po_item_name: str | None = None
    po_item_unit: str | None = None
    quantity_delta: Decimal

    model_config = ConfigDict(from_attributes=True)


class PoReceiveEventResponse(BaseModel):
    id: int
    workspace_id: int
    purchase_order_id: int
    event_type: str
    rcc: str | None = None
    received_by: str | None = None
    correction_note: str | None = None
    performed_by: int | None = None
    performer_name: str | None = None
    created_at: datetime
    items: List[PoReceiveEventItemResponse] = []

    model_config = ConfigDict(from_attributes=True)
