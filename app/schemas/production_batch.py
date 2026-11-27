"""Production Batch schemas"""
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ProductionBatchBase(BaseModel):
    """Base production batch schema"""
    production_line_id: int
    formula_id: int | None = None
    batch_date: date
    shift: str | None = Field(None, max_length=20)
    status: str = Field(default='draft', pattern=r'^(draft|in_progress|completed|cancelled)$')
    expected_output_quantity: int | None = Field(None, gt=0)
    expected_duration_minutes: int | None = Field(None, ge=0)
    actual_output_quantity: int | None = Field(None, gt=0)
    actual_duration_minutes: int | None = Field(None, ge=0)
    actual_start_time: datetime | None = None
    actual_end_time: datetime | None = None
    notes: str | None = None


class ProductionBatchCreate(ProductionBatchBase):
    """
    Production batch creation schema.
    workspace_id, batch_number, and created_by are injected by service.
    """


class ProductionBatchUpdate(BaseModel):
    """Production batch update schema"""
    formula_id: int | None = None
    batch_date: date | None = None
    shift: str | None = Field(None, max_length=20)
    status: str | None = Field(None, pattern=r'^(draft|in_progress|completed|cancelled)$')
    expected_output_quantity: int | None = Field(None, gt=0)
    expected_duration_minutes: int | None = Field(None, ge=0)
    actual_output_quantity: int | None = Field(None, gt=0)
    actual_duration_minutes: int | None = Field(None, ge=0)
    actual_start_time: datetime | None = None
    actual_end_time: datetime | None = None
    notes: str | None = None


class ProductionBatchInDB(ProductionBatchBase):
    """Production batch schema as stored in database"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    batch_number: str
    output_variance_quantity: int | None = None
    output_variance_percentage: Decimal | None = None
    efficiency_percentage: Decimal | None = None
    created_by: int | None = None
    updated_by: int | None = None
    created_at: datetime
    updated_at: datetime
    started_by: int | None = None
    started_at: datetime | None = None
    completed_by: int | None = None
    completed_at: datetime | None = None


class ProductionBatchResponse(ProductionBatchInDB):
    """Production batch response schema"""

    finished_goods_posted: bool = False
    """
    True when outputs for this batch have been posted to factory finished goods (products).
    Only guaranteed accurate on GET /production-batches/{id}/; list endpoints may omit or default.
    """


class ProductionBatchStatsResponse(BaseModel):
    """Aggregate production batch counts for dashboard KPIs."""
    in_progress_count: int
    total_count: int
