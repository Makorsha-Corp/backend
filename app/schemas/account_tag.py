"""Account tag schemas"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime


class AccountTagBase(BaseModel):
    """Base account tag schema"""
    name: str = Field(..., min_length=1, max_length=100)
    tag_code: str = Field(..., min_length=1, max_length=50)
    color: Optional[str] = Field(None, max_length=7, pattern=r'^#[0-9A-Fa-f]{6}$')
    icon: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = None


class AccountTagCreate(BaseModel):
    """Schema for creating an account tag (workspace_id injected by service)"""
    name: str = Field(..., min_length=1, max_length=100)
    tag_code: Optional[str] = Field(None, min_length=1, max_length=50)  # Optional, auto-generated from name
    color: Optional[str] = Field(None, max_length=7, pattern=r'^#[0-9A-Fa-f]{6}$')
    icon: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = None


class AccountTagUpdate(BaseModel):
    """Schema for updating an account tag"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    tag_code: Optional[str] = Field(None, min_length=1, max_length=50)
    color: Optional[str] = Field(None, max_length=7, pattern=r'^#[0-9A-Fa-f]{6}$')
    icon: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = None
    is_active: Optional[bool] = None


class AccountTagInDB(AccountTagBase):
    """Account tag schema as stored in database"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    is_system_tag: bool
    is_active: bool
    usage_count: int
    created_at: datetime
    created_by: Optional[int]


class AccountTagResponse(AccountTagInDB):
    """Account tag response schema"""
    pass
