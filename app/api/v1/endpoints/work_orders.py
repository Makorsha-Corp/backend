"""
Work order API endpoints

Provides operations for managing work orders and their items.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_workspace, get_current_active_user
from app.models.workspace import Workspace
from app.models.profile import Profile
from app.models.enums import WorkTypeEnum, WorkOrderPriorityEnum, WorkOrderStatusEnum
from app.schemas.work_order import WorkOrderCreate, WorkOrderUpdate, WorkOrderResponse
from app.schemas.work_order_item import WorkOrderItemCreate, WorkOrderItemUpdate, WorkOrderItemResponse
from app.services.work_order_service import work_order_service


router = APIRouter()


# ─── Work Orders ────────────────────────────────────────────────

@router.get(
    "/",
    response_model=List[WorkOrderResponse],
    status_code=status.HTTP_200_OK,
    summary="List work orders"
)
def list_work_orders(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    work_type: Optional[WorkTypeEnum] = Query(None),
    wo_status: Optional[WorkOrderStatusEnum] = Query(None, alias="status"),
    priority: Optional[WorkOrderPriorityEnum] = Query(None),
    factory_id: Optional[int] = Query(None),
    machine_id: Optional[int] = Query(None),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    return work_order_service.list_work_orders(
        db, workspace_id=workspace.id,
        work_type=work_type, wo_status=wo_status, priority=priority,
        factory_id=factory_id, machine_id=machine_id,
        skip=skip, limit=limit
    )


@router.get(
    "/{wo_id}/",
    response_model=WorkOrderResponse,
    status_code=status.HTTP_200_OK,
    summary="Get work order by ID"
)
def get_work_order(
    wo_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    return work_order_service.get_work_order(db, wo_id=wo_id, workspace_id=workspace.id)


@router.post(
    "/",
    response_model=WorkOrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create work order"
)
def create_work_order(
    wo_in: WorkOrderCreate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return work_order_service.create_work_order(
        db, wo_in=wo_in,
        workspace_id=workspace.id, user_id=current_user.id
    )


@router.put(
    "/{wo_id}/",
    response_model=WorkOrderResponse,
    status_code=status.HTTP_200_OK,
    summary="Update work order"
)
def update_work_order(
    wo_id: int,
    wo_in: WorkOrderUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return work_order_service.update_work_order(
        db, wo_id=wo_id, wo_in=wo_in,
        workspace_id=workspace.id, user_id=current_user.id
    )


@router.delete(
    "/{wo_id}/",
    response_model=WorkOrderResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete work order"
)
def delete_work_order(
    wo_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return work_order_service.delete_work_order(
        db, wo_id=wo_id,
        workspace_id=workspace.id, user_id=current_user.id
    )


# ─── Work Order Items ──────────────────────────────────────────

@router.get(
    "/{wo_id}/items/",
    response_model=List[WorkOrderItemResponse],
    status_code=status.HTTP_200_OK,
    summary="Get work order items"
)
def get_work_order_items(
    wo_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    return work_order_service.get_items(db, wo_id=wo_id, workspace_id=workspace.id)


@router.post(
    "/{wo_id}/items/",
    response_model=WorkOrderItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add item to work order"
)
def add_work_order_item(
    wo_id: int,
    item_in: WorkOrderItemCreate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    item_in.work_order_id = wo_id
    return work_order_service.add_item(
        db, item_in=item_in,
        workspace_id=workspace.id, user_id=current_user.id
    )


@router.put(
    "/items/{item_id}/",
    response_model=WorkOrderItemResponse,
    status_code=status.HTTP_200_OK,
    summary="Update work order item"
)
def update_work_order_item(
    item_id: int,
    item_in: WorkOrderItemUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    return work_order_service.update_item(
        db, item_id=item_id, item_in=item_in,
        workspace_id=workspace.id
    )


@router.delete(
    "/items/{item_id}/",
    response_model=WorkOrderItemResponse,
    status_code=status.HTTP_200_OK,
    summary="Remove item from work order"
)
def remove_work_order_item(
    item_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    return work_order_service.remove_item(
        db, item_id=item_id, workspace_id=workspace.id
    )
