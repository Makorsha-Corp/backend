"""Storage item schemas"""
from pydantic import BaseModel, ConfigDict


class StorageItemBase(BaseModel):
    """Base storage item schema"""
    factory_id: int
    item_id: int
    qty: int    
    avg_price: float | None = None


class StorageItemCreate(StorageItemBase):
    """Storage item creation schema"""
    pass


class StorageItemUpdate(BaseModel):
    """Storage item update schema"""
    qty: int | None = None
    avg_price: float | None = None


class StorageItemResponse(StorageItemBase):
    """Storage item response schema"""
    id: int

    model_config = ConfigDict(from_attributes=True)
