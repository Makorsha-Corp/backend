"""Project component item schemas"""
from pydantic import BaseModel, ConfigDict


class ProjectComponentItemBase(BaseModel):
    """Base project component item schema"""
    project_component_id: int
    item_id: int
    qty: int


class ProjectComponentItemCreate(ProjectComponentItemBase):
    """Project component item creation schema"""
    pass


class ProjectComponentItemUpdate(BaseModel):
    """Project component item update schema"""
    qty: int | None = None


class ProjectComponentItemResponse(ProjectComponentItemBase):
    """Project component item response schema"""
    id: int

    model_config = ConfigDict(from_attributes=True)
