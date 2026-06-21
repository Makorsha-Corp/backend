"""Notification schemas."""
from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict


class NotificationActor(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id:   int
    name: str


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id:                int
    workspace_id:      int
    notification_type: str
    entity_type:       str
    entity_id:         int
    source_type:       str
    source_id:         int
    preview:           Optional[str]
    is_read:           bool
    read_at:           Optional[datetime]
    created_at:        datetime
    actor:             Optional[NotificationActor] = None


class NotificationListResponse(BaseModel):
    items:        List[NotificationResponse]
    total:        int
    unread_count: int


class MarkReadRequest(BaseModel):
    ids: Optional[List[int]] = None   # null/omitted = mark all as read
