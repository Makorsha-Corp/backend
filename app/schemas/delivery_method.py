"""Delivery method schemas"""
from pydantic import BaseModel, ConfigDict


class DeliveryMethodBase(BaseModel):
    """Base delivery method schema"""
    name: str


class DeliveryMethodCreate(DeliveryMethodBase):
    """Delivery method creation schema"""
    pass


class DeliveryMethodUpdate(BaseModel):
    """Delivery method update schema"""
    name: str | None = None


class DeliveryMethodResponse(DeliveryMethodBase):
    """Delivery method response schema"""
    id: int

    model_config = ConfigDict(from_attributes=True)
