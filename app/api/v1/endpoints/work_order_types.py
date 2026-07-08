"""
Work order type API endpoints

Provides operations for managing user-defined work order types.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_active_user, get_current_workspace
from app.models.profile import Profile
from app.models.workspace import Workspace
from app.schemas.work_order_type import WorkOrderTypeCreate, WorkOrderTypeUpdate, WorkOrderTypeResponse
from app.services.work_order_type_service import work_order_type_service


router = APIRouter()


@router.get(
    "/",
    response_model=List[WorkOrderTypeResponse],
    status_code=status.HTTP_200_OK,
    summary="List all work order types",
    description="Get all work order types in the workspace with optional search"
)
def get_work_order_types(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: Optional[str] = Query(None, description="Search by name"),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    return work_order_type_service.get_work_order_types(
        db, workspace_id=workspace.id, search=search, skip=skip, limit=limit
    )


@router.get(
    "/{type_id}/",
    response_model=WorkOrderTypeResponse,
    status_code=status.HTTP_200_OK,
    summary="Get work order type by ID",
)
def get_work_order_type(
    type_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    return work_order_type_service.get_work_order_type(db, type_id=type_id, workspace_id=workspace.id)


@router.post(
    "/",
    response_model=WorkOrderTypeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new work order type",
)
def create_work_order_type(
    type_in: WorkOrderTypeCreate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return work_order_type_service.create_work_order_type(
        db, type_in=type_in, workspace_id=workspace.id, user_id=current_user.id
    )


@router.put(
    "/{type_id}/",
    response_model=WorkOrderTypeResponse,
    status_code=status.HTTP_200_OK,
    summary="Update work order type",
)
def update_work_order_type(
    type_id: int,
    type_in: WorkOrderTypeUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return work_order_type_service.update_work_order_type(
        db, type_id=type_id, type_in=type_in, workspace_id=workspace.id, user_id=current_user.id
    )


@router.delete(
    "/{type_id}/",
    response_model=WorkOrderTypeResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete work order type",
)
def delete_work_order_type(
    type_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return work_order_type_service.delete_work_order_type(
        db, type_id=type_id, workspace_id=workspace.id, user_id=current_user.id
    )
