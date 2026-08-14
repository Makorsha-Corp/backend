"""Attachment ledger schemas."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AttachmentLedgerCreate(BaseModel):
    workspace_id: int
    attachment_id: int
    transaction_type: str
    entity_type: str | None = None
    entity_id: int | None = None
    file_name: str
    mime_type: str
    file_size: int
    notes: str | None = None
    performed_by: int | None = None


class AttachmentLedgerUpdate(BaseModel):
    """Only notes may be amended (immutable ledger)."""
    notes: str | None = None


class AttachmentLedgerResponse(BaseModel):
    id: int
    workspace_id: int
    attachment_id: int
    transaction_type: str
    entity_type: str | None = None
    entity_id: int | None = None
    file_name: str
    mime_type: str
    file_size: int
    notes: str | None = None
    performed_by: int | None = None
    performed_at: datetime

    model_config = ConfigDict(from_attributes=True)
