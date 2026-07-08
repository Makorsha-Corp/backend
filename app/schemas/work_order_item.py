"""Work order item schemas"""
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class WorkOrderItemCreate(BaseModel):
    """Create work order item"""
    work_order_id: int
    item_id: int
    quantity: int
    notes: str | None = None


class WorkOrderItemUpdate(BaseModel):
    """Update work order item"""
    quantity: int | None = None
    notes: str | None = None


class WorkOrderItemResponse(BaseModel):
    """Work order item response"""
    id: int
    workspace_id: int
    work_order_id: int
    item_id: int
    item_name: str | None = None
    item_unit: str | None = None
    quantity: int
    notes: str | None = None
    created_at: datetime
    created_by: int | None = None

    model_config = ConfigDict(from_attributes=True)
