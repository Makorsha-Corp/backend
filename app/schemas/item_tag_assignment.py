"""Item tag assignment schemas"""
from pydantic import BaseModel, ConfigDict
from datetime import datetime


class ItemTagAssignmentBase(BaseModel):
    """Base item tag assignment schema"""
    item_id: int
    tag_id: int


class ItemTagAssignmentCreate(ItemTagAssignmentBase):
    """Item tag assignment creation schema - workspace_id injected by service layer"""
    pass


class ItemTagAssignmentResponse(ItemTagAssignmentBase):
    """Item tag assignment response schema"""
    id: int
    workspace_id: int
    assigned_at: datetime
    assigned_by: int | None = None

    model_config = ConfigDict(from_attributes=True)


class ItemWithTagsResponse(BaseModel):
    """Item with its tags response"""
    id: int
    workspace_id: int
    name: str
    description: str | None = None
    unit: str
    sku: str | None = None
    is_active: bool
    tags: list[str]  # List of tag_codes

    model_config = ConfigDict(from_attributes=True)
