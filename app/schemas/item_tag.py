"""Item tag schemas"""
from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime


class ItemTagBase(BaseModel):
    """Base item tag schema"""
    name: str = Field(..., min_length=1, max_length=100)
    tag_code: str = Field(..., min_length=1, max_length=50, pattern="^[a-z0-9_]+$")
    color: str | None = Field(None, pattern="^#[0-9A-Fa-f]{6}$")
    icon: str | None = Field(None, max_length=50)
    description: str | None = None


class ItemTagCreate(BaseModel):
    """Item tag creation schema - workspace_id injected by service layer"""
    name: str = Field(..., min_length=1, max_length=100)
    tag_code: str | None = Field(None, min_length=1, max_length=50, pattern="^[a-z0-9_]+$")  # Optional, auto-generated from name
    color: str | None = Field(None, pattern="^#[0-9A-Fa-f]{6}$")
    icon: str | None = Field(None, max_length=50)
    description: str | None = None


class ItemTagUpdate(BaseModel):
    """Item tag update schema"""
    name: str | None = Field(None, min_length=1, max_length=100)
    color: str | None = Field(None, pattern="^#[0-9A-Fa-f]{6}$")
    icon: str | None = Field(None, max_length=50)
    description: str | None = None
    is_active: bool | None = None


class ItemTagResponse(ItemTagBase):
    """Item tag response schema"""
    id: int
    workspace_id: int
    is_system_tag: bool
    is_active: bool
    usage_count: int
    created_at: datetime
    created_by: int | None = None

    model_config = ConfigDict(from_attributes=True)
