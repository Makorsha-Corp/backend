"""Department schemas"""
from pydantic import BaseModel, ConfigDict


class DepartmentBase(BaseModel):
    """Base department schema"""
    name: str


class DepartmentCreate(DepartmentBase):
    """Department creation schema"""
    pass


class DepartmentUpdate(BaseModel):
    """Department update schema"""
    name: str | None = None


class DepartmentResponse(DepartmentBase):
    """Department response schema"""
    id: int

    model_config = ConfigDict(from_attributes=True)
