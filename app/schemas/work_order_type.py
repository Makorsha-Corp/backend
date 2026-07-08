"""Work order type schemas"""
from pydantic import BaseModel, ConfigDict


class WorkOrderTypeBase(BaseModel):
    """Base work order type schema"""
    name: str


class WorkOrderTypeCreate(WorkOrderTypeBase):
    """Work order type creation schema"""
    pass


class WorkOrderTypeUpdate(BaseModel):
    """Work order type update schema"""
    name: str | None = None


class WorkOrderTypeResponse(WorkOrderTypeBase):
    """Work order type response schema"""
    id: int

    model_config = ConfigDict(from_attributes=True)
