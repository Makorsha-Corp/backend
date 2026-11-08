"""
Production Batch endpoints

Provides CRUD and workflow operations for production batches.
Batches track actual production runs with expected vs actual variance analysis.
Supports both formula-driven (with auto-calculated expected values) and
simple mode (manual tracking).
"""
from datetime import date, datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_active_user, get_current_workspace
from app.models.profile import Profile
from app.models.workspace import Workspace
from app.schemas.production_batch import (
    ProductionBatchCreate,
    ProductionBatchUpdate,
    ProductionBatchResponse,
    ProductionBatchStatsResponse,
    ProductionOverviewStatsResponse,
    ProductionBatchActivityResponse,
    ProductionScheduleBatch,
    StageLogScheduleMoveResponse,
    LinkedProductionOrdersResponse,
)
from app.schemas.production_batch_item import (
    ProductionBatchItemCreate,
    ProductionBatchItemUpdate,
    ProductionBatchItemResponse,
)
from app.schemas.production_batch_stage_log import (
    ProductionBatchStageLogCreate,
    ProductionBatchStageLogUpdate,
    ProductionBatchStageLogResponse,
    StageLogAsPlannedRequest,
    StageLogFinishRequest,
    StageLogStartRequest,
    StageLogScheduleMoveRequest,
)
from app.schemas.production_batch_stage_item import (
    ProductionBatchStageItemResponse,
    ProductionBatchStageItemUpdate,
)
from app.schemas.production_batch_stage_parameter import (
    ProductionBatchStageParameterResponse,
    ProductionBatchStageParameterUpdate,
)
from app.schemas.production_batch_event import ProductionBatchEventResponse
from app.services.production_batch_service import production_batch_service
from app.dao.product_ledger import product_ledger_dao
from app.models.production_batch import ProductionBatch as ProductionBatchModel


router = APIRouter()


def _batch_response(db: Session, workspace_id: int, batch: ProductionBatchModel) -> ProductionBatchResponse:
    posted = product_ledger_dao.exists_for_production_batch(
        db, workspace_id=workspace_id, batch_id=batch.id
    )
    return ProductionBatchResponse.model_validate(batch).model_copy(
        update={"finished_goods_posted": posted}
    )


# ─── Workflow Request Schemas ────────────────────────────────────────

class StartBatchRequest(BaseModel):
    """Request body for starting a batch"""
    target_output_quantity: Optional[int] = Field(
        None, gt=0,
        description="Target output quantity. If omitted, uses sum of formula's product items."
    )
    started_at: Optional[datetime] = None


class CompleteBatchRequest(BaseModel):
    """Request body for completing a batch"""
    actual_output_quantity: Optional[int] = Field(None, gt=0, description="Actual output produced")
    actual_duration_minutes: Optional[int] = Field(None, ge=0, description="Actual time taken in minutes")
    notes: Optional[str] = Field(None, description="Completion notes")
    completed_at: Optional[datetime] = None


class PostFinishedGoodsRequest(BaseModel):
    """Optional body when posting a completed batch to finished goods."""

    include_byproducts: bool = Field(
        True,
        description="Include byproduct lines when posting quantities.",
    )


class CancelBatchRequest(BaseModel):
    """Request body for cancelling a batch"""
    notes: Optional[str] = Field(None, description="Cancellation reason")


# ─── Batch Endpoints ────────────────────────────────────────────────


@router.get(
    "/",
    response_model=List[ProductionBatchResponse],
    status_code=status.HTTP_200_OK,
    summary="List production batches",
    description="""
    Get all production batches with optional filtering by production line,
    formula, or status. Supports pagination. Results ordered by batch_date descending.
    """,
)
def get_batches(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    production_line_id: Optional[int] = Query(None, description="Filter by production line ID"),
    formula_id: Optional[int] = Query(None, description="Filter by formula ID"),
    batch_status: Optional[str] = Query(
        None, alias="status",
        description="Filter by status: draft, recurring, in_progress, completed, cancelled"
    ),
    sales_order_item_id: Optional[int] = Query(None, description="Filter by sales order line"),
    factory_id: Optional[int] = Query(None, description="Filter by factory (via production line)"),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    """Get all production batches with optional filters"""
    return production_batch_service.get_batches(
        db,
        workspace_id=workspace.id,
        production_line_id=production_line_id,
        formula_id=formula_id,
        status=batch_status,
        sales_order_item_id=sales_order_item_id,
        factory_id=factory_id,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/stats/",
    response_model=ProductionBatchStatsResponse,
    status_code=status.HTTP_200_OK,
    summary="Production batch KPI stats",
    description="Aggregate batch counts for dashboard KPIs.",
)
def get_batch_stats(
    factory_id: Optional[int] = Query(None, description="Filter in-progress batches by factory"),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    stats = production_batch_service.get_batch_stats(
        db, workspace_id=workspace.id, factory_id=factory_id
    )
    return ProductionBatchStatsResponse(**stats)


@router.get(
    "/stats/overview/",
    response_model=ProductionOverviewStatsResponse,
    status_code=status.HTTP_200_OK,
    summary="Production overview stats by line and recipe",
)
def get_overview_stats(
    factory_id: Optional[int] = Query(None, description="Optional factory scope"),
    production_line_id: Optional[int] = Query(None, description="Optional line filter"),
    date_from: Optional[date] = Query(None, description="Batch date from (default: 90 days ago)"),
    date_to: Optional[date] = Query(None, description="Batch date to (default: today)"),
    statuses: Optional[str] = Query(
        None,
        description="Comma-separated batch statuses to include (draft,recurring,in_progress,completed,cancelled)",
    ),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    today = date.today()
    effective_to = date_to or today
    effective_from = date_from or (effective_to - timedelta(days=90))
    status_list = [s.strip() for s in statuses.split(",") if s.strip()] if statuses else None
    stats = production_batch_service.get_overview_stats(
        db,
        workspace_id=workspace.id,
        factory_id=factory_id,
        date_from=effective_from,
        date_to=effective_to,
        production_line_id=production_line_id,
        statuses=status_list,
    )
    return ProductionOverviewStatsResponse(**stats)


@router.get(
    "/stats/activity/",
    response_model=ProductionBatchActivityResponse,
    status_code=status.HTTP_200_OK,
    summary="Batch counts by day for activity heatmap",
)
def get_batch_activity_stats(
    factory_id: Optional[int] = Query(None, description="Optional factory scope"),
    production_line_id: Optional[List[int]] = Query(
        None, description="Optional line filters (repeat param or comma-separated)"
    ),
    formula_id: Optional[List[int]] = Query(
        None, description="Optional recipe filters (repeat param or comma-separated)"
    ),
    date_from: Optional[date] = Query(None, description="Batch date from (default: 12 months ago)"),
    date_to: Optional[date] = Query(None, description="Batch date to (default: today)"),
    statuses: Optional[str] = Query(
        None,
        description="Comma-separated batch statuses to include",
    ),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    today = date.today()
    effective_to = date_to or today
    effective_from = date_from or (effective_to - timedelta(days=365))
    status_list = [s.strip() for s in statuses.split(",") if s.strip()] if statuses else None

    def _expand_ids(values: Optional[List[int]]) -> Optional[List[int]]:
        if not values:
            return None
        out: List[int] = []
        for raw in values:
            for part in str(raw).split(","):
                part = part.strip()
                if part.isdigit():
                    out.append(int(part))
        return out or None

    line_ids = _expand_ids(production_line_id)
    formula_ids = _expand_ids(formula_id)
    payload = production_batch_service.get_batch_activity_counts(
        db,
        workspace_id=workspace.id,
        factory_id=factory_id,
        date_from=effective_from,
        date_to=effective_to,
        production_line_ids=line_ids,
        formula_ids=formula_ids,
        statuses=status_list,
    )
    return ProductionBatchActivityResponse(**payload)


@router.post(
    "/",
    response_model=ProductionBatchResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create production batch",
    description="""
    Create a new production batch in 'draft' status.
    Requires a production_line_id. Optionally attach a formula_id for
    formula-driven production with variance tracking.
    Batch number is auto-generated (e.g., B-2025-001).
    """,
)
def create_batch(
    batch_in: ProductionBatchCreate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Create new production batch"""
    return production_batch_service.create_batch(
        db, batch_in, workspace.id, current_user.id
    )


# ─── Batch Workflow Endpoints ────────────────────────────────────────


@router.post(
    "/{batch_id}/start/",
    response_model=ProductionBatchResponse,
    status_code=status.HTTP_200_OK,
    summary="Start production batch",
    description="""
    Start a production batch (draft or recurring -> in_progress).

    If the batch has a formula attached:
    - Calculates expected input/output quantities based on target_output_quantity
    - Creates batch items from formula items with scaled expected quantities
    - Sets expected_duration_minutes from formula

    If no formula (simple mode):
    - Just transitions to in_progress status

    Optionally provide target_output_quantity to scale the formula.
    If omitted, uses the formula's base output_quantity.
    """,
)
def start_batch(
    batch_id: int,
    body: StartBatchRequest,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Start a production batch"""
    return production_batch_service.start_batch(
        db, batch_id, workspace.id, current_user.id,
        target_output_quantity=body.target_output_quantity,
        started_at=body.started_at,
    )


@router.post(
    "/{batch_id}/revert-to-draft/",
    response_model=ProductionBatchResponse,
    status_code=status.HTTP_200_OK,
    summary="Return recurring batch to draft",
    description="Only recurring batches can move back to draft for editing before start.",
)
def revert_batch_to_draft(
    batch_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return production_batch_service.revert_batch_to_draft(
        db, batch_id, workspace.id, current_user.id
    )


@router.post(
    "/{batch_id}/complete/",
    response_model=ProductionBatchResponse,
    status_code=status.HTTP_200_OK,
    summary="Complete production batch",
    description="""
    Complete a production batch (in_progress -> completed).

    Provide actual output quantity and duration. The system will automatically
    calculate variance metrics:
    - output_variance_quantity (actual - expected)
    - output_variance_percentage
    - efficiency_percentage (actual / expected * 100)

    Also calculates per-item variance for batch items that have actual_quantity set.
    """,
)
def complete_batch(
    batch_id: int,
    body: CompleteBatchRequest,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Complete a production batch"""
    result = production_batch_service.complete_batch(
        db,
        batch_id,
        workspace.id,
        current_user.id,
        actual_output_quantity=body.actual_output_quantity,
        actual_duration_minutes=body.actual_duration_minutes,
        notes=body.notes,
        completed_at=body.completed_at,
    )
    return _batch_response(db, workspace.id, result)


@router.post(
    "/{batch_id}/post-finished-goods/",
    response_model=ProductionBatchResponse,
    status_code=status.HTTP_200_OK,
    summary="Post batch outputs to finished goods",
    description="""
    For a **completed** batch, add output and optional byproduct quantities to factory
    finished goods (`products`, not-for-sale bucket). Each batch can only be posted once.

    Quantities come from batch line actuals (fallback: expected), or from batch actual output
    when the formula defines a single output item.
    """,
)
def post_finished_goods(
    batch_id: int,
    body: PostFinishedGoodsRequest = PostFinishedGoodsRequest(),
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    result = production_batch_service.post_outputs_to_finished_goods(
        db,
        batch_id,
        workspace.id,
        current_user.id,
        include_byproducts=body.include_byproducts,
    )
    return _batch_response(db, workspace.id, result)


@router.post(
    "/{batch_id}/cancel/",
    response_model=ProductionBatchResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancel production batch",
    description="Cancel a draft or in-progress batch. Provide optional cancellation notes.",
)
def cancel_batch(
    batch_id: int,
    body: CancelBatchRequest,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Cancel a production batch"""
    return production_batch_service.cancel_batch(
        db, batch_id, workspace.id, current_user.id,
        notes=body.notes
    )


# ─── Batch Item Endpoints ───────────────────────────────────────────


@router.get(
    "/{batch_id}/items/",
    response_model=List[ProductionBatchItemResponse],
    status_code=status.HTTP_200_OK,
    summary="List batch items",
    description="""
    Get all items for a production batch.
    Optionally filter by item_role (input, output, waste, byproduct).
    """,
)
def get_batch_items(
    batch_id: int,
    item_role: Optional[str] = Query(
        None,
        description="Filter by item role: input, output, waste, byproduct",
        pattern=r'^(input|output|waste|byproduct)$'
    ),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    """Get all items for a batch"""
    return production_batch_service.get_batch_items(
        db, batch_id, workspace_id=workspace.id, item_role=item_role
    )


@router.post(
    "/{batch_id}/items/",
    response_model=ProductionBatchItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add item to batch",
    description="""
    Add an item to a production batch (manual entry).
    Only for draft or in_progress batches.
    item_role must be one of: input, output, waste, byproduct.
    """,
)
def add_batch_item(
    batch_id: int,
    item_in: ProductionBatchItemCreate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Add an item to a batch"""
    if item_in.batch_id != batch_id:
        from app.core.exceptions import BusinessRuleError
        raise BusinessRuleError(
            f"Path batch_id ({batch_id}) does not match body batch_id ({item_in.batch_id})"
        )
    return production_batch_service.add_batch_item(
        db, item_in, workspace.id, user_id=current_user.id
    )


@router.put(
    "/items/{batch_item_id}/",
    response_model=ProductionBatchItemResponse,
    status_code=status.HTTP_200_OK,
    summary="Update batch item",
    description="""
    Update a batch item (e.g., log actual quantities, set source/destination).
    Only for draft or in_progress batches.
    """,
)
def update_batch_item(
    batch_item_id: int,
    item_in: ProductionBatchItemUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Update a batch item"""
    return production_batch_service.update_batch_item(
        db, batch_item_id, item_in, workspace.id, current_user.id
    )


@router.delete(
    "/items/{batch_item_id}/",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove item from batch",
    description="Remove an item from a batch (hard delete). Only for draft or in_progress batches.",
)
def remove_batch_item(
    batch_item_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Remove an item from a batch"""
    production_batch_service.remove_batch_item(db, batch_item_id, workspace.id)


# ─── Batch stage parameter endpoints ────────────────────────────────


@router.get(
    "/{batch_id}/stage-parameters/",
    response_model=List[ProductionBatchStageParameterResponse],
    status_code=status.HTTP_200_OK,
    summary="List all step conditions for a batch",
)
def get_batch_stage_parameters(
    batch_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    return production_batch_service.get_batch_stage_parameters(db, batch_id, workspace.id)


@router.get(
    "/{batch_id}/stage-logs/{log_id}/parameters/",
    response_model=List[ProductionBatchStageParameterResponse],
    status_code=status.HTTP_200_OK,
    summary="List step conditions for a batch stage log",
)
def get_batch_stage_log_parameters(
    batch_id: int,
    log_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    return production_batch_service.get_batch_stage_log_parameters(
        db, batch_id, log_id, workspace.id
    )


@router.patch(
    "/stage-parameters/{parameter_id}/",
    response_model=ProductionBatchStageParameterResponse,
    status_code=status.HTTP_200_OK,
    summary="Patch batch step condition (planned and/or actual)",
)
def update_batch_stage_parameter(
    parameter_id: int,
    param_in: ProductionBatchStageParameterUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return production_batch_service.update_batch_stage_parameter(
        db, parameter_id, param_in, workspace.id, current_user.id
    )


@router.patch(
    "/{batch_id}/stage-logs/{log_id}/parameters/by-source/{source_parameter_id}/",
    response_model=ProductionBatchStageParameterResponse,
    status_code=status.HTTP_200_OK,
    summary="Patch step condition by formula source (creates batch row if missing)",
)
def set_batch_stage_parameter_by_source(
    batch_id: int,
    log_id: int,
    source_parameter_id: int,
    param_in: ProductionBatchStageParameterUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return production_batch_service.set_batch_stage_parameter_by_source(
        db,
        batch_id,
        log_id,
        source_parameter_id,
        param_in,
        workspace.id,
        current_user.id,
    )


@router.get(
    "/{batch_id}/stage-items/",
    response_model=List[ProductionBatchStageItemResponse],
    status_code=status.HTTP_200_OK,
    summary="List per-step material rows for a batch",
)
def get_batch_stage_items(
    batch_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    return production_batch_service.get_batch_stage_items(db, batch_id, workspace.id)


@router.patch(
    "/stage-items/{item_row_id}/",
    response_model=ProductionBatchStageItemResponse,
    status_code=status.HTTP_200_OK,
    summary="Set a pending step input actual quantity",
)
def update_batch_stage_item(
    item_row_id: int,
    item_in: ProductionBatchStageItemUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user),
):
    return production_batch_service.update_batch_stage_item_actual(
        db,
        item_row_id,
        item_in.actual_quantity,
        workspace.id,
        user_id=current_user.id,
    )


# ─── Batch Stage Log Endpoints ──────────────────────────────────────


@router.get(
    "/{batch_id}/stage-logs/",
    response_model=List[ProductionBatchStageLogResponse],
    status_code=status.HTTP_200_OK,
    summary="List batch stage logs",
)
def get_batch_stage_logs(
    batch_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    return production_batch_service.get_batch_stage_logs(db, batch_id, workspace.id)


@router.post(
    "/{batch_id}/stage-logs/",
    response_model=ProductionBatchStageLogResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add batch stage log",
)
def add_batch_stage_log(
    batch_id: int,
    log_in: ProductionBatchStageLogCreate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    if log_in.batch_id != batch_id:
        from app.core.exceptions import BusinessRuleError
        raise BusinessRuleError(
            f"Path batch_id ({batch_id}) does not match body batch_id ({log_in.batch_id})"
        )
    return production_batch_service.add_batch_stage_log(
        db, log_in, workspace.id, current_user.id
    )


@router.patch(
    "/stage-logs/{log_id}/",
    response_model=ProductionBatchStageLogResponse,
    status_code=status.HTTP_200_OK,
    summary="Update batch stage log",
)
def update_batch_stage_log(
    log_id: int,
    log_in: ProductionBatchStageLogUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return production_batch_service.update_batch_stage_log(
        db, log_id, log_in, workspace.id, current_user.id
    )


@router.get("/schedule/", response_model=List[ProductionScheduleBatch])
def get_production_schedule(
    factory_id: Optional[int] = Query(None, description="Optional factory scope"),
    start: datetime = Query(...),
    end: datetime = Query(...),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    return production_batch_service.get_schedule(db, workspace.id, factory_id, start, end)


@router.post(
    "/stage-logs/{log_id}/move-on-schedule/",
    response_model=StageLogScheduleMoveResponse,
)
def move_stage_log_on_schedule(
    log_id: int,
    body: StageLogScheduleMoveRequest,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return production_batch_service.move_stage_log_on_schedule(
        db,
        log_id,
        workspace.id,
        current_user.id,
        production_line_id=body.production_line_id,
        planned_start_at=body.planned_start_at,
        machine_id=body.machine_id,
    )


@router.get("/{batch_id}/linked-orders/", response_model=LinkedProductionOrdersResponse)
def get_linked_orders(
    batch_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    return production_batch_service.linked_orders(db, batch_id, workspace.id)


@router.post("/stage-logs/{log_id}/start/", response_model=ProductionBatchStageLogResponse)
def start_stage_log(
    log_id: int,
    body: StageLogStartRequest,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return production_batch_service.start_stage_log(
        db, log_id, workspace.id, current_user.id, started_at=body.started_at, machine_id=body.machine_id
    )


@router.post("/stage-logs/{log_id}/finish/", response_model=ProductionBatchStageLogResponse)
def finish_stage_log(
    log_id: int,
    body: StageLogFinishRequest,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return production_batch_service.finish_stage_log(
        db,
        log_id,
        workspace.id,
        current_user.id,
        output_quantity=body.output_quantity,
        completed_at=body.completed_at,
        input_quantity=body.input_quantity,
        waste_quantity=body.waste_quantity,
        rework_quantity=body.rework_quantity,
        rework_to_log_id=body.rework_to_log_id,
        notes=body.notes,
    )


@router.post("/stage-logs/{log_id}/log-as-planned/", response_model=ProductionBatchStageLogResponse)
def log_stage_as_planned(
    log_id: int,
    body: StageLogAsPlannedRequest,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return production_batch_service.log_stage_as_planned(
        db,
        log_id,
        workspace.id,
        current_user.id,
        output_quantity=body.output_quantity,
        input_quantity=body.input_quantity,
        waste_quantity=body.waste_quantity,
        notes=body.notes,
    )


# ─── Batch by ID (after /{batch_id}/… sub-routes to avoid routing ambiguity) ──


@router.get(
    "/{batch_id}/events/",
    response_model=List[ProductionBatchEventResponse],
    status_code=status.HTTP_200_OK,
    summary="List batch activity events",
)
def list_batch_events(
    batch_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    return production_batch_service.list_batch_events(
        db, batch_id, workspace.id, skip=skip, limit=limit
    )


@router.get(
    "/{batch_id}/",
    response_model=ProductionBatchResponse,
    status_code=status.HTTP_200_OK,
    summary="Get production batch by ID",
    description="Retrieve a single production batch by its ID. Raises 404 if not found.",
)
def get_batch(
    batch_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    """Get production batch by ID"""
    batch = production_batch_service.get_batch(db, batch_id, workspace_id=workspace.id)
    return _batch_response(db, workspace.id, batch)


@router.put(
    "/{batch_id}/",
    response_model=ProductionBatchResponse,
    status_code=status.HTTP_200_OK,
    summary="Update production batch",
    description="""
    Update a production batch. Only draft or in_progress batches can be updated.
    Status changes must use the dedicated workflow endpoints (start, complete, cancel).
    """,
)
def update_batch(
    batch_id: int,
    batch_in: ProductionBatchUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Update production batch"""
    return production_batch_service.update_batch(
        db, batch_id, batch_in, workspace.id, current_user.id
    )


@router.delete(
    "/{batch_id}/",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete production batch",
    description="Cancel a draft batch. Only draft batches can be deleted. Returns 204 on success.",
)
def delete_batch(
    batch_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Delete (cancel) a draft production batch"""
    production_batch_service.delete_batch(db, batch_id, workspace.id, current_user.id)
