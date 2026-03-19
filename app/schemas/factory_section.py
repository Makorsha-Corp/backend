"""Factory section schemas"""
from pydantic import BaseModel, ConfigDict


class FactorySectionBase(BaseModel):
    """Base factory section schema"""
    name: str
    factory_id: int


class FactorySectionCreate(FactorySectionBase):
    """Factory section creation schema"""
    pass


class FactorySectionUpdate(BaseModel):
    """Factory section update schema"""
    name: str | None = None
    factory_id: int | None = None


class FactorySectionResponse(FactorySectionBase):
    """Factory section response schema"""
    id: int

    model_config = ConfigDict(from_attributes=True)
