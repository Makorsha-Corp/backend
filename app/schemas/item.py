"""Item schemas (renamed from Part)"""
from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import List, Literal


class ItemBase(BaseModel):
    """Base item schema"""
    name: str
    description: str | None = None
    unit: str
    sku: str | None = None
    item_type: Literal["physical", "service"] = "physical"


class ItemCreate(ItemBase):
    """Item creation schema - workspace_id injected by service layer"""
    tag_ids: List[int] = []  # List of tag IDs to assign


class ItemUpdate(BaseModel):
    """Item update schema"""
    name: str | None = None
    description: str | None = None
    unit: str | None = None
    sku: str | None = None
    item_type: Literal["physical", "service"] | None = None
    is_active: bool | None = None
    tag_ids: List[int] | None = None  # Update tags if provided


class ItemResponse(ItemBase):
    """Item response schema"""
    id: int
    workspace_id: int
    created_at: datetime
    updated_at: datetime | None = None
    created_by: int | None = None
    updated_by: int | None = None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class ItemWithTagsResponse(ItemBase):
    """Item response schema with tags included"""
    id: int
    workspace_id: int
    created_at: datetime
    updated_at: datetime | None = None
    created_by: int | None = None
    updated_by: int | None = None
    is_active: bool
    tags: List[dict] = []  # List of tag objects with id, name, tag_code, color, icon

    model_config = ConfigDict(from_attributes=True)


class ItemListResponse(BaseModel):
    """Paginated active items with tags for catalog list views."""
    items: List[ItemWithTagsResponse] = Field(default_factory=list)
    total: int = 0
    skip: int = 0
    limit: int = 0
    has_more: bool = False
