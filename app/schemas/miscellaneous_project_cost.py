"""Miscellaneous project cost schemas"""
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class MiscellaneousProjectCostBase(BaseModel):
    """Base miscellaneous project cost schema"""
    project_id: int | None = None
    project_component_id: int | None = None
    name: str
    description: str | None = None
    amount: float


class MiscellaneousProjectCostCreate(MiscellaneousProjectCostBase):
    """Miscellaneous project cost creation schema"""
    pass


class MiscellaneousProjectCostUpdate(BaseModel):
    """Miscellaneous project cost update schema"""
    name: str | None = None
    description: str | None = None
    amount: float | None = None


class MiscellaneousProjectCostResponse(MiscellaneousProjectCostBase):
    """Miscellaneous project cost response schema"""
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
