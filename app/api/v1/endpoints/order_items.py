"""Order item endpoints"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_active_user, get_current_workspace
from app.models.profile import Profile
from app.models.workspace import Workspace
from app.schemas.order_item import OrderItemCreate, OrderItemUpdate, OrderItemResponse
from app.services.order_item_service import order_item_service


router = APIRouter()


@router.get("/", response_model=List[OrderItemResponse])
def get_order_items(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=100),
    order_id: int = Query(None),
    pending_approval: bool = Query(None),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Get all order items, optionally filtered by order or approval status"""
    return order_item_service.get_items(db, workspace_id=workspace.id, order_id=order_id, pending_approval=pending_approval, skip=skip, limit=limit)


@router.get("/{order_item_id}/", response_model=OrderItemResponse)
def get_order_item(
    order_item_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Get order item by ID"""
    item = order_item_service.get_by_id(db, item_id=order_item_id, workspace_id=workspace.id)
    if not item:
        raise HTTPException(status_code=404, detail="Order item not found")
    return item


@router.post("/", response_model=OrderItemResponse, status_code=201)
def create_order_item(
    part_in: OrderItemCreate,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Create new order item"""
    return order_item_service.create_item(db, item_in=part_in, workspace_id=workspace.id)


@router.put("/{order_item_id}/", response_model=OrderItemResponse)
def update_order_item(
    order_item_id: int,
    item_in: OrderItemUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Update order item"""
    item = order_item_service.update_item(db, item_id=order_item_id, item_in=item_in, workspace_id=workspace.id)
    if not item:
        raise HTTPException(status_code=404, detail="Order item not found")
    return item


@router.delete("/{order_item_id}/", status_code=204)
def delete_order_item(
    order_item_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Delete order item (soft delete)"""
    deleted = order_item_service.delete_item(db, item_id=order_item_id, workspace_id=workspace.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Order item not found")
