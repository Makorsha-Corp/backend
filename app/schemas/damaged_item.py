"""Damaged item schemas"""
from pydantic import BaseModel, ConfigDict


class DamagedItemBase(BaseModel):
    """Base damaged item schema"""
    factory_id: int
    item_id: int
    qty: int
    avg_price: float | None = None


class DamagedItemCreate(DamagedItemBase):
    """Damaged item creation schema"""
    pass


class DamagedItemUpdate(BaseModel):
    """Damaged item update schema"""
    qty: int | None = None
    avg_price: float | None = None


class DamagedItemResponse(DamagedItemBase):
    """Damaged item response schema"""
    id: int

    model_config = ConfigDict(from_attributes=True)
