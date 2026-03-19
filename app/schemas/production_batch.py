"""Production Batch schemas"""
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional
from datetime import datetime, date
from decimal import Decimal


class ProductionBatchBase(BaseModel):
    """Base production batch schema"""
    production_line_id: int
    formula_id: Optional[int] = None
    batch_date: date
    shift: Optional[str] = Field(None, max_length=20)
    status: str = Field(default='draft', pattern=r'^(draft|in_progress|completed|cancelled)$')
    expected_output_quantity: Optional[int] = Field(None, gt=0)
    expected_duration_minutes: Optional[int] = Field(None, ge=0)
    actual_output_quantity: Optional[int] = Field(None, gt=0)
    actual_duration_minutes: Optional[int] = Field(None, ge=0)
    actual_start_time: Optional[datetime] = None
    actual_end_time: Optional[datetime] = None
    notes: Optional[str] = None


class ProductionBatchCreate(ProductionBatchBase):
    """
    Production batch creation schema.
    workspace_id, batch_number, and created_by are injected by service.
    """
    pass


class ProductionBatchUpdate(BaseModel):
    """Production batch update schema"""
    formula_id: Optional[int] = None
    batch_date: Optional[date] = None
    shift: Optional[str] = Field(None, max_length=20)
    status: Optional[str] = Field(None, pattern=r'^(draft|in_progress|completed|cancelled)$')
    expected_output_quantity: Optional[int] = Field(None, gt=0)
    expected_duration_minutes: Optional[int] = Field(None, ge=0)
    actual_output_quantity: Optional[int] = Field(None, gt=0)
    actual_duration_minutes: Optional[int] = Field(None, ge=0)
    actual_start_time: Optional[datetime] = None
    actual_end_time: Optional[datetime] = None
    notes: Optional[str] = None


class ProductionBatchInDB(ProductionBatchBase):
    """Production batch schema as stored in database"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    batch_number: str
    output_variance_quantity: Optional[int] = None
    output_variance_percentage: Optional[Decimal] = None
    efficiency_percentage: Optional[Decimal] = None
    created_by: Optional[int] = None
    updated_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    started_by: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_by: Optional[int] = None
    completed_at: Optional[datetime] = None


class ProductionBatchResponse(ProductionBatchInDB):
    """Production batch response schema"""
    pass
