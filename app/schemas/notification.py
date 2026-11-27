"""Notification schemas."""
from __future__ import annotations

from datetime import datetime

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
    entity_label:      str
    source_type:       str
    source_id:         int
    preview:           str | None
    is_read:           bool
    read_at:           datetime | None
    created_at:        datetime
    actor:             NotificationActor | None = None


class NotificationListResponse(BaseModel):
    items:        list[NotificationResponse]
    total:        int
    unread_count: int


class MarkReadRequest(BaseModel):
    ids: list[int] | None = None   # null/omitted = mark all as read
