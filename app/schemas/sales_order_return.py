from datetime import datetime
from decimal import Decimal
from typing import List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator


class SalesOrderReturnItemCreate(BaseModel):
    so_item_id: int
    quantity_returned: Decimal
    unit_price: Optional[Decimal] = None
    notes: Optional[str] = None


class SalesOrderReturnCreate(BaseModel):
    return_type: Literal['replace', 'refund']
    reason: Optional[str] = None
    notes: Optional[str] = None
    items: List[SalesOrderReturnItemCreate]

    @model_validator(mode='after')
    def validate_return(self) -> 'SalesOrderReturnCreate':
        if not self.items:
            raise ValueError('At least one item must be selected for return')
        for item in self.items:
            if item.quantity_returned <= 0:
                raise ValueError('All return quantities must be positive')
        return self


class SalesOrderReturnVoidRequest(BaseModel):
    void_note: str = Field(..., min_length=1, description="Required reason for cancelling the return")


class SalesOrderReturnItemResponse(BaseModel):
    id: int
    return_id: int
    so_item_id: int
    item_id: Optional[int] = None
    item_name: Optional[str] = None
    item_unit: Optional[str] = None
    quantity_returned: Decimal
    unit_price: Optional[Decimal] = None
    notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class SalesOrderReturnResponse(BaseModel):
    id: int
    workspace_id: int
    sales_order_id: int
    return_number: str
    status: str
    return_type: str
    invoice_id: Optional[int] = None
    paid: bool
    reason: Optional[str] = None
    notes: Optional[str] = None
    completed_at: Optional[datetime] = None
    completed_by: Optional[int] = None
    created_by: int
    created_at: datetime
    items: List[SalesOrderReturnItemResponse] = []

    model_config = ConfigDict(from_attributes=True)
