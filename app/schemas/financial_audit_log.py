"""Financial audit log schemas"""
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class FinancialAuditLogResponse(BaseModel):
    """Response schema for financial audit log"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    entity_type: str
    entity_id: int
    action_type: str
    related_entity_type: str | None = None
    related_entity_id: int | None = None
    changes: dict[str, Any] | None = None
    description: str | None = None
    performed_by: int
    performed_at: datetime
    ip_address: str | None = None
    user_agent: str | None = None
