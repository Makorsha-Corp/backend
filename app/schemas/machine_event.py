"""Machine event schemas"""
from datetime import datetime
from pydantic import BaseModel, ConfigDict
from app.models.enums import MachineEventTypeEnum


class MachineEventBase(BaseModel):
    """Base machine event schema"""
    machine_id: int
    event_type: MachineEventTypeEnum
    note: str | None = None


class MachineEventCreate(MachineEventBase):
    """Machine event creation schema"""
    pass


class MachineEventUpdate(BaseModel):
    """Machine event update schema - only note can be updated (events are immutable)"""
    note: str | None = None


class MachineEventResponse(BaseModel):
    """Machine event response schema"""
    id: int
    workspace_id: int
    machine_id: int
    event_type: MachineEventTypeEnum
    started_at: datetime
    initiated_by: int | None = None
    note: str | None = None
    created_at: datetime
    created_by: int | None = None

    model_config = ConfigDict(from_attributes=True)
