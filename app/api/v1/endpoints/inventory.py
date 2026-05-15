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
from app.schemas.inventory import InventoryCreate, InventoryUpdate, InventoryResponse
from app.services.inventory_service import inventory_service


router = APIRouter()


@router.get(
    "/",
    response_model=List[InventoryResponse],
    status_code=status.HTTP_200_OK,
    summary="List inventory records",
    description="Get all inventory records, optionally filtered by type or factory"
)
def list_inventory(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    inventory_type: Optional[InventoryTypeEnum] = Query(None, description="Filter by inventory type"),
    factory_id: Optional[int] = Query(None, description="Filter by factory ID"),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    return inventory_service.list_inventory(
        db, workspace_id=workspace.id,
        inventory_type=inventory_type, factory_id=factory_id,
        skip=skip, limit=limit
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
    summary="Delete inventory record"
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
