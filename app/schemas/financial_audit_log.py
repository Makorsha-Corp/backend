"""Financial audit log schemas"""
from pydantic import BaseModel, ConfigDict
from typing import Optional, Dict, Any
from datetime import datetime


class FinancialAuditLogResponse(BaseModel):
    """Response schema for financial audit log"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    entity_type: str
    entity_id: int
    action_type: str
    related_entity_type: Optional[str] = None
    related_entity_id: Optional[int] = None
    changes: Optional[Dict[str, Any]] = None
    description: Optional[str] = None
    performed_by: int
    performed_at: datetime
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
