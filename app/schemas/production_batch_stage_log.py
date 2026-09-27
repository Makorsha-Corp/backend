"""Production batch stage log schemas"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

VALID_STAGE_LOG_STATUSES = ("pending", "in_progress", "completed", "skipped")


class ProductionBatchStageLogBase(BaseModel):
    stage_name: str = Field(..., min_length=1, max_length=200)
    stage_order: int = Field(default=0, ge=0)
    production_line_id: int | None = None
    status: str = Field(default="pending", pattern=r"^(pending|in_progress|completed|skipped)$")
    started_at: datetime | None = None
    completed_at: datetime | None = None
    input_quantity: int | None = Field(None, ge=0)
    output_quantity: int | None = Field(None, ge=0)
    waste_quantity: int | None = Field(None, ge=0)
    notes: str | None = None


class ProductionBatchStageLogCreate(ProductionBatchStageLogBase):
    batch_id: int
    formula_stage_id: int | None = None


class ProductionBatchStageLogUpdate(BaseModel):
    stage_name: str | None = Field(None, min_length=1, max_length=200)
    stage_order: int | None = Field(None, ge=0)
    production_line_id: int | None = None
    status: str | None = Field(None, pattern=r"^(pending|in_progress|completed|skipped)$")
    started_at: datetime | None = None
    completed_at: datetime | None = None
    input_quantity: int | None = Field(None, ge=0)
    output_quantity: int | None = Field(None, ge=0)
    waste_quantity: int | None = Field(None, ge=0)
    notes: str | None = None


class ProductionBatchStageLogInDB(ProductionBatchStageLogBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    batch_id: int
    formula_stage_id: int | None = None
    logged_by: int | None = None
    created_at: datetime
    updated_at: datetime


class ProductionBatchStageLogResponse(ProductionBatchStageLogInDB):
    pass
