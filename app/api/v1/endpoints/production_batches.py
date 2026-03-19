"""
Production Batch endpoints

Provides CRUD and workflow operations for production batches.
Batches track actual production runs with expected vs actual variance analysis.
Supports both formula-driven (with auto-calculated expected values) and
simple mode (manual tracking).
"""
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
)
from app.schemas.production_batch_item import (
    ProductionBatchItemCreate,
    ProductionBatchItemUpdate,
    ProductionBatchItemResponse,
)
from app.services.production_batch_service import production_batch_service


router = APIRouter()


# ─── Workflow Request Schemas ────────────────────────────────────────

class StartBatchRequest(BaseModel):
    """Request body for starting a batch"""
    target_output_quantity: Optional[int] = Field(
        None, gt=0,
        description="Target output quantity. If omitted, uses sum of formula's product items."
    )


class CompleteBatchRequest(BaseModel):
    """Request body for completing a batch"""
    actual_output_quantity: Optional[int] = Field(None, gt=0, description="Actual output produced")
    actual_duration_minutes: Optional[int] = Field(None, ge=0, description="Actual time taken in minutes")
    notes: Optional[str] = Field(None, description="Completion notes")


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
    limit: int = Query(100, le=100, description="Maximum number of records to return"),
    production_line_id: Optional[int] = Query(None, description="Filter by production line ID"),
    formula_id: Optional[int] = Query(None, description="Filter by formula ID"),
    batch_status: Optional[str] = Query(
        None, alias="status",
        description="Filter by status: draft, in_progress, completed, cancelled"
    ),
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
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{batch_id}",
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
    return production_batch_service.get_batch(
        db, batch_id, workspace_id=workspace.id
    )


@router.post(
    "/",
    response_model=ProductionBatchResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create production batch",
    description="""
    Create a new production batch in 'draft' status.
    Requires a production_line_id. Optionally attach a formula_id for
    formula-driven production with variance tracking.
    Batch number is auto-generated (e.g., BATCH-2025-001).
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


@router.put(
    "/{batch_id}",
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
    "/{batch_id}",
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
    production_batch_service.delete_batch(db, batch_id, workspace.id)


# ─── Batch Workflow Endpoints ────────────────────────────────────────


@router.post(
    "/{batch_id}/start",
    response_model=ProductionBatchResponse,
    status_code=status.HTTP_200_OK,
    summary="Start production batch",
    description="""
    Start a production batch (draft -> in_progress).

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
        target_output_quantity=body.target_output_quantity
    )


@router.post(
    "/{batch_id}/complete",
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
    return production_batch_service.complete_batch(
        db, batch_id, workspace.id, current_user.id,
        actual_output_quantity=body.actual_output_quantity,
        actual_duration_minutes=body.actual_duration_minutes,
        notes=body.notes
    )


@router.post(
    "/{batch_id}/cancel",
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
    "/{batch_id}/items",
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
    "/{batch_id}/items",
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
        db, item_in, workspace.id
    )


@router.put(
    "/items/{batch_item_id}",
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
        db, batch_item_id, item_in, workspace.id
    )


@router.delete(
    "/items/{batch_item_id}",
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
