"""Discussion schemas."""
from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, field_validator
from app.models.enums import DiscussionEntityType


class DiscussionCreate(BaseModel):
    entity_type: DiscussionEntityType
    entity_id:   int
    message:     str
    parent_id:   Optional[int] = None

    @field_validator("message")
    @classmethod
    def message_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Message cannot be empty")
        return v


class DiscussionAuthor(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id:   int
    name: str


class DiscussionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:          int
    workspace_id: int
    entity_type: str
    entity_id:   int
    message:     str
    parent_id:   Optional[int]
    created_at:  datetime
    author:      Optional[DiscussionAuthor] = None
    replies:     List[DiscussionResponse] = []


class DiscussionListResponse(BaseModel):
    items: List[DiscussionResponse]
    total: int
