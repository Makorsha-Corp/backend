"""
Unified inventory API endpoints (STORAGE, DAMAGED, WASTE, SCRAP).

Inventory ledger queries live at `/api/v1/ledgers/inventory/*` — this module
only handles inventory snapshot CRUD.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_workspace, get_current_active_user
from app.models.workspace import Workspace
from app.models.profile import Profile
from app.models.enums import InventoryTypeEnum
from app.schemas.inventory import (
    InventoryCreate,
    InventoryUpdate,
    InventoryResponse,
    InventoryListResponse,
    InventoryStatsResponse,
)
from app.schemas.inventory_incoming import ItemIncomingSummary
from app.services.inventory_service import inventory_service


router = APIRouter()


@router.get(
    "/",
    response_model=InventoryListResponse,
    status_code=status.HTTP_200_OK,
    summary="List inventory records",
    description=(
        "Paginated inventory list with optional filters. "
        "Returns `{ items, total, skip, limit, has_more }`."
    ),
)
def list_inventory(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=1000),
    inventory_type: Optional[InventoryTypeEnum] = Query(None, description="Filter by inventory type"),
    factory_id: Optional[int] = Query(None, description="Filter by factory ID"),
    search: Optional[str] = Query(None, description="Search item name or unit"),
    item_id: Optional[int] = Query(None, description="Filter by catalog item ID"),
    include_zero_qty: bool = Query(False, description="Include rows with zero quantity"),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    return inventory_service.get_inventory_page(
        db,
        workspace_id=workspace.id,
        inventory_type=inventory_type,
        factory_id=factory_id,
        item_id=item_id,
        search=search,
        include_zero_qty=include_zero_qty,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/stats/",
    response_model=InventoryStatsResponse,
    status_code=status.HTTP_200_OK,
    summary="Inventory hub KPI stats",
    description="Aggregate counts and values for the current inventory filter set.",
)
def get_inventory_stats(
    inventory_type: Optional[InventoryTypeEnum] = Query(None, description="Filter by inventory type"),
    factory_id: Optional[int] = Query(None, description="Filter by factory ID"),
    search: Optional[str] = Query(None, description="Search item name or unit"),
    item_id: Optional[int] = Query(None, description="Filter by catalog item ID"),
    include_zero_qty: bool = Query(False, description="Include rows with zero quantity"),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    return inventory_service.get_inventory_stats(
        db,
        workspace_id=workspace.id,
        inventory_type=inventory_type,
        factory_id=factory_id,
        item_id=item_id,
        search=search,
        include_zero_qty=include_zero_qty,
    )


@router.get(
    "/incoming-summary/",
    response_model=List[ItemIncomingSummary],
    status_code=status.HTTP_200_OK,
    summary="Incoming order summary by item",
    description=(
        "Pending quantities per catalog item from open purchase orders and "
        "inbound transfer orders destined for factory storage."
    ),
    tags=["inventory"],
)
def get_incoming_summary(
    factory_id: Optional[int] = Query(None, description="Factory ID; omit for all factories"),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    return inventory_service.get_incoming_summary(
        db, workspace_id=workspace.id, factory_id=factory_id
    )


@router.get(
    "/{inv_id}/",
    response_model=InventoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get inventory record by ID"
)
def get_inventory(
    inv_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    return inventory_service.get_inventory(db, inv_id=inv_id, workspace_id=workspace.id)


@router.post(
    "/",
    response_model=InventoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create inventory record"
)
def create_inventory(
    inv_in: InventoryCreate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return inventory_service.create_inventory(
        db, inv_in=inv_in,
        workspace_id=workspace.id, user_id=current_user.id
    )


@router.put(
    "/{inv_id}/",
    response_model=InventoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Update inventory record"
)
def update_inventory(
    inv_id: int,
    inv_in: InventoryUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return inventory_service.update_inventory(
        db, inv_id=inv_id, inv_in=inv_in,
        workspace_id=workspace.id, user_id=current_user.id
    )


@router.delete(
    "/{inv_id}/",
    response_model=InventoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Clear inventory stock",
    description="Set quantity to zero and record an inventory_adjustment in the ledger. The row remains active.",
)
def delete_inventory(
    inv_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return inventory_service.delete_inventory(
        db, inv_id=inv_id,
        workspace_id=workspace.id, user_id=current_user.id
    )
