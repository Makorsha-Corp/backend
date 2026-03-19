"""Order item endpoints"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_active_user
from app.models.profile import Profile
from app.schemas.order_item import OrderItemCreate, OrderItemUpdate, OrderItemResponse
from app.dao.order_item import order_item_dao


router = APIRouter()


@router.get("/", response_model=List[OrderItemResponse])
def get_order_items(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=100),
    order_id: int = Query(None),
    pending_approval: bool = Query(None),
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Get all order items, optionally filtered by order or approval status"""
    if order_id:
        items = order_item_dao.get_by_order(db, order_id=order_id, skip=skip, limit=limit)
    elif pending_approval:
        items = order_item_dao.get_pending_approval(db, skip=skip, limit=limit)
    else:
        items = order_item_dao.get_multi(db, skip=skip, limit=limit)
    return items


@router.get("/{order_item_id}", response_model=OrderItemResponse)
def get_order_item(
    order_item_id: int,
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Get order item by ID"""
    item = order_item_dao.get(db, id=order_item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Order item not found")
    return item


@router.post("/", response_model=OrderItemResponse, status_code=201)
def create_order_item(
    part_in: OrderItemCreate,
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Create new order item"""
    item = order_item_dao.create(db, obj_in=part_in)
    return item


@router.put("/{order_item_id}", response_model=OrderItemResponse)
def update_order_item(
    order_item_id: int,
    item_in: OrderItemUpdate,
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Update order item"""
    item = order_item_dao.get(db, id=order_item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Order item not found")
    item = order_item_dao.update(db, db_obj=item, obj_in=item_in)
    return item


@router.delete("/{order_item_id}", status_code=204)
def delete_order_item(
    order_item_id: int,
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Delete order item (soft delete)"""
    item = order_item_dao.get(db, id=order_item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Order item not found")

    # Soft delete - just mark as deleted
    from datetime import datetime
    item = order_item_dao.update(
        db,
        db_obj=item,
        obj_in={"is_deleted": True, "deleted_at": datetime.utcnow()}
    )
