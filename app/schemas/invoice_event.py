"""Invoice event schemas"""
from pydantic import BaseModel, ConfigDict
from typing import Optional, Any
from datetime import datetime


class InvoiceEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    invoice_id: int
    event_type: str
    description: str
    metadata_json: Optional[Any] = None
    performed_by: Optional[int] = None
    performed_by_name: Optional[str] = None
    created_at: datetime
