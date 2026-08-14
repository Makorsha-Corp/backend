"""Help ticket schemas."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import HelpTicketStatusEnum


class HelpTicketCreate(BaseModel):
    """Create a new help ticket."""
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1)
    category: str | None = Field(default=None, max_length=80)


class HelpTicketUpdate(BaseModel):
    """Update ticket fields or close/reopen."""
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, min_length=1)
    category: str | None = Field(default=None, max_length=80)
    status: HelpTicketStatusEnum | None = None


class HelpTicketResponse(BaseModel):
    """Help ticket API response."""
    id: int
    workspace_id: int
    ticket_number: str
    title: str
    description: str
    category: str | None
    status: HelpTicketStatusEnum
    created_by: int | None
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None
    closed_by: int | None

    model_config = ConfigDict(from_attributes=True)
