"""Production batch stage log schemas"""
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional


VALID_STAGE_LOG_STATUSES = ("pending", "in_progress", "completed", "skipped")


class ProductionBatchStageLogBase(BaseModel):
    stage_name: str = Field(..., min_length=1, max_length=200)
    stage_order: int = Field(default=0, ge=0)
    production_line_id: Optional[int] = None
    status: str = Field(default="pending", pattern=r"^(pending|in_progress|completed|skipped)$")
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    input_quantity: Optional[int] = Field(None, ge=0)
    output_quantity: Optional[int] = Field(None, ge=0)
    waste_quantity: Optional[int] = Field(None, ge=0)
    notes: Optional[str] = None


class ProductionBatchStageLogCreate(ProductionBatchStageLogBase):
    batch_id: int
    formula_stage_id: Optional[int] = None


class ProductionBatchStageLogUpdate(BaseModel):
    stage_name: Optional[str] = Field(None, min_length=1, max_length=200)
    stage_order: Optional[int] = Field(None, ge=0)
    production_line_id: Optional[int] = None
    status: Optional[str] = Field(None, pattern=r"^(pending|in_progress|completed|skipped)$")
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    input_quantity: Optional[int] = Field(None, ge=0)
    output_quantity: Optional[int] = Field(None, ge=0)
    waste_quantity: Optional[int] = Field(None, ge=0)
    notes: Optional[str] = None


class ProductionBatchStageLogInDB(ProductionBatchStageLogBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    batch_id: int
    formula_stage_id: Optional[int] = None
    logged_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class ProductionBatchStageLogResponse(ProductionBatchStageLogInDB):
    pass
