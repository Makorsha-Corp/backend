"""Factory schemas"""
from pydantic import BaseModel, ConfigDict


class FactoryBase(BaseModel):
    """Base factory schema"""
    name: str
    abbreviation: str


class FactoryCreate(FactoryBase):
    """Factory creation schema"""
    pass


class FactoryUpdate(BaseModel):
    """Factory update schema"""
    name: str | None = None
    abbreviation: str | None = None


class FactoryResponse(FactoryBase):
    """Factory response schema"""
    id: int

    model_config = ConfigDict(from_attributes=True)
