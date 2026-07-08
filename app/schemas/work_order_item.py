"""Work order item schemas"""
from datetime import datetime
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict

WorkOrderItemActionType = Literal['CONSUME', 'INSTALL', 'REPLACE', 'BORROW']


class WorkOrderItemCreate(BaseModel):
    """Create work order item"""
    work_order_id: int
    item_id: int
    quantity: Decimal = Decimal("1")
    notes: str | None = None
    uses_inventory: bool = False
    source_location_type: str | None = None  # 'storage' | 'machine'
    source_location_id: int | None = None
    action_type: WorkOrderItemActionType = 'CONSUME'
    replaced_item_id: int | None = None  # only used when action_type == 'REPLACE'


class WorkOrderItemUpdate(BaseModel):
    """Update work order item"""
    quantity: Decimal | None = None
    notes: str | None = None
    uses_inventory: bool | None = None
    source_location_type: str | None = None
    source_location_id: int | None = None


class WorkOrderItemResponse(BaseModel):
    """Work order item response"""
    id: int
    workspace_id: int
    work_order_id: int
    item_id: int
    item_name: str | None = None
    item_unit: str | None = None
    quantity: Decimal
    notes: str | None = None

    uses_inventory: bool
    source_location_type: str | None = None
    source_location_id: int | None = None
    action_type: WorkOrderItemActionType
    replaced_item_id: int | None = None
    replaced_item_name: str | None = None

    consumed_at: datetime | None = None
    consumed_by: int | None = None
    unit_cost: Decimal | None = None
    total_cost: Decimal | None = None

    created_at: datetime
    created_by: int | None = None
    updated_at: datetime | None = None
    updated_by: int | None = None

    model_config = ConfigDict(from_attributes=True)
