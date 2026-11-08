"""Production batch activity event schemas."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProductionBatchEventResponse(BaseModel):
    id: int
    workspace_id: int
    batch_id: int
    batch_stage_log_id: int | None = None
    event_type: str
    description: str
    metadata: dict | None = None
    performed_by: int | None = None
    user_name: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProductionBatchEventListParams(BaseModel):
    skip: int = Field(0, ge=0)
    limit: int = Field(100, ge=1, le=200)
