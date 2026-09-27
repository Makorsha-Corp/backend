from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PurchaseOrderReturnItemCreate(BaseModel):
    po_item_id: int
    quantity_returned: Decimal
    unit_price: Decimal | None = None
    notes: str | None = None


class PurchaseOrderReturnCreate(BaseModel):
    return_type: Literal['replace', 'refund']
    reason: str | None = None
    notes: str | None = None
    items: list[PurchaseOrderReturnItemCreate]

    @model_validator(mode='after')
    def validate_return(self) -> 'PurchaseOrderReturnCreate':
        if not self.items:
            raise ValueError('At least one item must be selected for return')
        for item in self.items:
            if item.quantity_returned <= 0:
                raise ValueError('All return quantities must be positive')
        return self


class PurchaseOrderReturnVoidRequest(BaseModel):
    void_note: str = Field(..., min_length=1, description="Required reason for cancelling the return")


class PurchaseOrderReturnItemResponse(BaseModel):
    id: int
    return_id: int
    po_item_id: int
    item_id: int
    item_name: str | None = None
    item_unit: str | None = None
    quantity_returned: Decimal
    unit_price: Decimal | None = None
    notes: str | None = None

    model_config = ConfigDict(from_attributes=True)


class PurchaseOrderReturnResponse(BaseModel):
    id: int
    workspace_id: int
    purchase_order_id: int
    return_number: str
    status: str
    return_type: str
    invoice_id: int | None = None
    paid: bool
    reason: str | None = None
    notes: str | None = None
    completed_at: datetime | None = None
    completed_by: int | None = None
    created_by: int
    created_at: datetime
    items: list[PurchaseOrderReturnItemResponse] = []

    model_config = ConfigDict(from_attributes=True)
