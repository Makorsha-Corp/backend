"""Workspace shift window schemas."""
from datetime import time, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class WorkspaceShiftBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    start_time: time
    end_time: time
    sort_order: int = Field(default=0, ge=0)
    is_active: bool = True


class WorkspaceShiftCreate(WorkspaceShiftBase):
    pass


class WorkspaceShiftUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=80)
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    sort_order: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None


class WorkspaceShiftResponse(WorkspaceShiftBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    created_at: datetime
    updated_at: datetime
