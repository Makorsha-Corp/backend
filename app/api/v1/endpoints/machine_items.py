"""
Machine item API endpoints

Provides operations for managing items assigned to machines.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_workspace, get_current_active_user
from app.models.workspace import Workspace
from app.models.profile import Profile
from app.schemas.machine_item import MachineItemCreate, MachineItemUpdate, MachineItemResponse
from app.services.machine_item_service import machine_item_service


router = APIRouter()


@router.get(
    "/",
    response_model=List[MachineItemResponse],
    status_code=status.HTTP_200_OK,
    summary="List machine items",
    description="Get all machine items in the workspace, optionally filtered by machine"
)
def get_machine_items(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    machine_id: Optional[int] = Query(None, description="Filter by machine ID"),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Get all machine items in workspace"""
    return machine_item_service.get_machine_items(
        db, workspace_id=workspace.id,
        machine_id=machine_id, skip=skip, limit=limit
    )


@router.get(
    "/{machine_item_id}/",
    response_model=MachineItemResponse,
    status_code=status.HTTP_200_OK,
    summary="Get machine item by ID"
)
def get_machine_item(
    machine_item_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Get a specific machine item"""
    return machine_item_service.get_machine_item(
        db, machine_item_id=machine_item_id, workspace_id=workspace.id
    )


@router.post(
    "/",
    response_model=MachineItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create machine item"
)
def create_machine_item(
    item_in: MachineItemCreate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Assign an item to a machine"""
    return machine_item_service.create_machine_item(
        db, item_in=item_in, workspace_id=workspace.id,
        user_id=current_user.id,
    )


@router.put(
    "/{machine_item_id}/",
    response_model=MachineItemResponse,
    status_code=status.HTTP_200_OK,
    summary="Update machine item"
)
def update_machine_item(
    machine_item_id: int,
    item_in: MachineItemUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update machine item quantities"""
    return machine_item_service.update_machine_item(
        db, machine_item_id=machine_item_id,
        item_in=item_in, workspace_id=workspace.id,
        user_id=current_user.id,
    )


@router.delete(
    "/{machine_item_id}/",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete machine item"
)
def delete_machine_item(
    machine_item_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Remove an item from a machine"""
    machine_item_service.delete_machine_item(
        db, machine_item_id=machine_item_id, workspace_id=workspace.id,
        user_id=current_user.id,
    )
