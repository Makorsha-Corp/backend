"""Invoice event schemas"""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class InvoiceEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    invoice_id: int
    event_type: str
    description: str
    metadata_json: Any | None = None
    performed_by: int | None = None
    performed_by_name: str | None = None
    created_at: datetime
