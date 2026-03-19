"""Order part log schemas"""
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class OrderPartLogBase(BaseModel):
    """Base order part log schema"""
    order_part_id: int
    action_on: str
    before: str
    after: str
    note: str | None = None


class OrderPartLogCreate(OrderPartLogBase):
    """Order part log creation schema"""
    updated_by: int


class OrderPartLogResponse(OrderPartLogBase):
    """Order part log response schema"""
    id: int
    updated_by: int
    updated_on: datetime

    model_config = ConfigDict(from_attributes=True)
