"""Transfer order API endpoints"""
from typing import List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_workspace, get_current_active_user
from app.models.workspace import Workspace
from app.models.profile import Profile
from app.schemas.transfer_order import (
    TransferOrderCreate, TransferOrderUpdate, TransferOrderResponse,
    TransferOrderItemCreate, TransferOrderItemUpdate, TransferOrderItemResponse,
)
from app.services.transfer_order_service import transfer_order_service


router = APIRouter()


# ─── Transfer Orders ───────────────────────────────────────────

@router.get(
    "/",
    response_model=List[TransferOrderResponse],
    status_code=status.HTTP_200_OK,
    summary="List transfer orders"
)
def list_transfer_orders(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    return transfer_order_service.list_transfer_orders(
        db, workspace_id=workspace.id,
        skip=skip, limit=limit
    )


@router.get(
    "/{to_id}",
    response_model=TransferOrderResponse,
    status_code=status.HTTP_200_OK,
    summary="Get transfer order by ID"
)
def get_transfer_order(
    to_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    return transfer_order_service.get_transfer_order(db, to_id=to_id, workspace_id=workspace.id)


@router.post(
    "/",
    response_model=TransferOrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create transfer order"
)
def create_transfer_order(
    to_in: TransferOrderCreate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return transfer_order_service.create_transfer_order(
        db, to_in=to_in,
        workspace_id=workspace.id, user_id=current_user.id
    )


@router.put(
    "/{to_id}",
    response_model=TransferOrderResponse,
    status_code=status.HTTP_200_OK,
    summary="Update transfer order"
)
def update_transfer_order(
    to_id: int,
    to_in: TransferOrderUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return transfer_order_service.update_transfer_order(
        db, to_id=to_id, to_in=to_in,
        workspace_id=workspace.id, user_id=current_user.id
    )


@router.delete(
    "/{to_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete transfer order"
)
def delete_transfer_order(
    to_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    transfer_order_service.delete_transfer_order(db, to_id=to_id, workspace_id=workspace.id)


# ─── Transfer Order Items ──────────────────────────────────────

@router.get(
    "/{to_id}/items",
    response_model=List[TransferOrderItemResponse],
    status_code=status.HTTP_200_OK,
    summary="Get transfer order items"
)
def get_transfer_order_items(
    to_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    return transfer_order_service.get_items(db, to_id=to_id, workspace_id=workspace.id)


@router.post(
    "/{to_id}/items",
    response_model=TransferOrderItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add item to transfer order"
)
def add_transfer_order_item(
    to_id: int,
    item_in: TransferOrderItemCreate,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    return transfer_order_service.add_item(
        db, to_id=to_id, item_in=item_in, workspace_id=workspace.id
    )


@router.put(
    "/items/{item_id}",
    response_model=TransferOrderItemResponse,
    status_code=status.HTTP_200_OK,
    summary="Update transfer order item"
)
def update_transfer_order_item(
    item_id: int,
    item_in: TransferOrderItemUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return transfer_order_service.update_item(
        db, item_id=item_id, item_in=item_in,
        workspace_id=workspace.id, user_id=current_user.id
    )


@router.delete(
    "/items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove item from transfer order"
)
def remove_transfer_order_item(
    item_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    transfer_order_service.remove_item(db, item_id=item_id, workspace_id=workspace.id)
