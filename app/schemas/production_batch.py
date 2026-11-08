"""Production Batch schemas"""
from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional
from datetime import datetime, date
from decimal import Decimal


class ProductionBatchStageSeed(BaseModel):
    """Optional override when seeding stage logs from a recipe at batch create."""
    formula_stage_id: int
    include: bool = True
    production_line_id: Optional[int] = None
    machine_id: Optional[int] = None
    expected_duration_minutes: Optional[int] = Field(None, ge=0)
    expected_output_quantity: Optional[Decimal] = Field(None, ge=0)


class ProductionBatchItemSeed(BaseModel):
    item_id: int
    item_role: str = Field(..., pattern=r"^(input|output|waste|byproduct)$")
    expected_quantity: Decimal = Field(..., ge=0)
    formula_stage_id: Optional[int] = None


class ProductionBatchStageParameterSeed(BaseModel):
    """Override recipe planned condition when seeding batch stage logs."""
    source_parameter_id: int
    planned_value: str = Field(..., min_length=1)


class ProductionBatchBase(BaseModel):
    """Base production batch schema"""
    production_line_id: int
    machine_id: Optional[int] = None
    formula_id: Optional[int] = None
    planned_start_at: Optional[datetime] = None
    sales_order_item_id: Optional[int] = None
    batch_date: date
    shift_id: Optional[int] = None
    shift: Optional[str] = Field(None, max_length=80)
    status: str = Field(default='draft', pattern=r'^(draft|recurring|in_progress|completed|cancelled)$')
    expected_output_quantity: Optional[Decimal] = Field(None, gt=0)
    expected_duration_minutes: Optional[int] = Field(None, ge=0)
    actual_output_quantity: Optional[Decimal] = Field(None, gt=0)
    actual_duration_minutes: Optional[int] = Field(None, ge=0)
    actual_start_time: Optional[datetime] = None
    actual_end_time: Optional[datetime] = None
    notes: Optional[str] = None


class ProductionBatchCreate(ProductionBatchBase):
    """
    Production batch creation schema.
    workspace_id, batch_number, and created_by are injected by service.
    """
    stage_seeds: Optional[List[ProductionBatchStageSeed]] = None
    item_seeds: Optional[List[ProductionBatchItemSeed]] = None
    parameter_seeds: Optional[List[ProductionBatchStageParameterSeed]] = None


class ProductionBatchUpdate(BaseModel):
    """Production batch update schema"""
    formula_id: Optional[int] = None
    machine_id: Optional[int] = None
    planned_start_at: Optional[datetime] = None
    sales_order_item_id: Optional[int] = None
    batch_date: Optional[date] = None
    shift_id: Optional[int] = None
    shift: Optional[str] = Field(None, max_length=80)
    status: Optional[str] = Field(None, pattern=r'^(draft|recurring|in_progress|completed|cancelled)$')
    actual_start_time: Optional[datetime] = None
    actual_end_time: Optional[datetime] = None
    notes: Optional[str] = None


class ProductionBatchInDB(ProductionBatchBase):
    """Production batch schema as stored in database"""
    model_config = ConfigDict(from_attributes=True)

    id: int
    workspace_id: int
    batch_number: str
    route_id: Optional[int] = None
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

    finished_goods_posted: bool = False
    planned_end_at: Optional[datetime] = None
    linked_spend_total: Optional[Decimal] = None
    sales_order_number: Optional[str] = None
    sales_account_name: Optional[str] = None
    """
    True when outputs for this batch have been posted to factory finished goods (products).
    Only guaranteed accurate on GET /production-batches/{id}/; list endpoints may omit or default.
    """


class ProductionBatchStatsResponse(BaseModel):
    """Aggregate production batch counts for dashboard KPIs."""
    in_progress_count: int
    total_count: int


class ProductionConditionDriftSummary(BaseModel):
    label: str
    unit: Optional[str] = None
    avg_drift: float
    steps_with_actual: int


class ProductionRecipeStatsRow(BaseModel):
    formula_id: Optional[int] = None
    recipe_name: str
    batch_count: int = 0
    output_quantity: Optional[float] = None
    waste_quantity: Optional[float] = None
    yield_pct: Optional[float] = None
    time_vs_plan_pct: Optional[float] = None
    avg_start_lag_minutes: Optional[float] = None
    late_start_count: int = 0
    avg_step_gap_minutes: Optional[float] = None
    condition_drifts: List[ProductionConditionDriftSummary] = []


class ProductionLineStatsRow(BaseModel):
    production_line_id: int
    line_name: str
    batch_count: int = 0
    output_quantity: Optional[float] = None
    waste_quantity: Optional[float] = None
    yield_pct: Optional[float] = None
    time_vs_plan_pct: Optional[float] = None
    avg_start_lag_minutes: Optional[float] = None
    late_start_count: int = 0
    avg_step_gap_minutes: Optional[float] = None
    recipes: List[ProductionRecipeStatsRow] = []


class ProductionBatchOutlierRow(BaseModel):
    batch_id: int
    batch_number: str
    production_line_id: int
    line_name: str
    formula_id: Optional[int] = None
    recipe_name: str
    metric: str
    delta_from_group: float


class ProductionOverviewStatsResponse(BaseModel):
    date_from: date
    date_to: date
    lines: List[ProductionLineStatsRow]
    outliers: List[ProductionBatchOutlierRow] = []


class ProductionBatchActivityDayCount(BaseModel):
    date: date
    count: int


class ProductionBatchActivityResponse(BaseModel):
    date_from: date
    date_to: date
    days: List[ProductionBatchActivityDayCount] = []


class ProductionScheduleStep(BaseModel):
    stage_log_id: int
    stage_name: str
    stage_order: int
    production_line_id: Optional[int] = None
    machine_id: Optional[int] = None
    status: str = "pending"
    planned_start_at: datetime
    planned_end_at: datetime
    rework_of_log_id: Optional[int] = None


class ProductionScheduleBatch(BaseModel):
    batch_id: int
    batch_number: str
    status: str
    machine_id: Optional[int] = None
    planned_start_at: datetime
    planned_end_at: datetime
    steps: list[ProductionScheduleStep]


class StageLogScheduleMoveResponse(BaseModel):
    batch_id: int
    planned_start_at: datetime
    steps: list[ProductionScheduleStep]


class LinkedProductionOrder(BaseModel):
    order_kind: str
    id: int
    number: str
    account_id: Optional[int] = None
    account_name: Optional[str] = None
    order_date: Optional[date] = None
    total_amount: Decimal
    voided: bool


class LinkedProductionOrdersResponse(BaseModel):
    orders: list[LinkedProductionOrder]
    linked_spend_total: Decimal
