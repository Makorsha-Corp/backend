"""Production batch stage log schemas"""
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional


VALID_STAGE_LOG_STATUSES = ("pending", "in_progress", "completed", "skipped")


class ProductionBatchStageLogBase(BaseModel):
    stage_name: str = Field(..., min_length=1, max_length=200)
    stage_order: int = Field(default=0, ge=0)
    production_line_id: Optional[int] = None
    machine_id: Optional[int] = None
    status: str = Field(default="pending", pattern=r"^(pending|in_progress|completed|skipped)$")
    planned_start_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    input_quantity: Optional[Decimal] = Field(None, ge=0)
    output_quantity: Optional[Decimal] = Field(None, ge=0)
    waste_quantity: Optional[Decimal] = Field(None, ge=0)
    notes: Optional[str] = None


class ProductionBatchStageLogCreate(ProductionBatchStageLogBase):
    batch_id: int
    formula_stage_id: Optional[int] = None


class ProductionBatchStageLogUpdate(BaseModel):
    stage_name: Optional[str] = Field(None, min_length=1, max_length=200)
    stage_order: Optional[int] = Field(None, ge=0)
    production_line_id: Optional[int] = None
    machine_id: Optional[int] = None
    expected_duration_minutes: Optional[int] = Field(None, ge=0)
    planned_start_at: Optional[datetime] = None
    status: Optional[str] = Field(None, pattern=r"^(pending|in_progress|completed|skipped)$")
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    input_quantity: Optional[Decimal] = Field(None, ge=0)
    output_quantity: Optional[Decimal] = Field(None, ge=0)
    waste_quantity: Optional[Decimal] = Field(None, ge=0)
    notes: Optional[str] = None


class ProductionBatchStageLogInDB(ProductionBatchStageLogBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    batch_id: int
    formula_stage_id: Optional[int] = None
    route_step_id: Optional[int] = None
    expected_duration_minutes: Optional[int] = None
    expected_output_quantity: Optional[Decimal] = None
    rework_quantity: Optional[Decimal] = None
    rework_of_log_id: Optional[int] = None
    logged_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class ProductionBatchStageLogResponse(ProductionBatchStageLogInDB):
    actual_duration_minutes: Optional[int] = None
    yield_pct: Optional[float] = None
    time_efficiency_pct: Optional[float] = None
    throughput_per_hour: Optional[float] = None
    waste_pct: Optional[float] = None


class StageLogStartRequest(BaseModel):
    started_at: Optional[datetime] = None
    machine_id: Optional[int] = None


class StageLogFinishRequest(BaseModel):
    completed_at: Optional[datetime] = None
    input_quantity: Optional[Decimal] = Field(None, ge=0)
    output_quantity: Decimal = Field(..., ge=0)
    waste_quantity: Optional[Decimal] = Field(None, ge=0)
    rework_quantity: Optional[Decimal] = Field(None, ge=0)
    rework_to_log_id: Optional[int] = None
    notes: Optional[str] = None


class StageLogAsPlannedRequest(BaseModel):
    output_quantity: Decimal = Field(..., ge=0)
    input_quantity: Optional[Decimal] = Field(None, ge=0)
    waste_quantity: Optional[Decimal] = Field(None, ge=0)
    notes: Optional[str] = None


class StageLogScheduleMoveRequest(BaseModel):
    production_line_id: int
    planned_start_at: datetime
    machine_id: Optional[int] = None
