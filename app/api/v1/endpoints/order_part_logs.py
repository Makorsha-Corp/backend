"""Order part log endpoints"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_active_user
from app.models.profile import Profile
from app.schemas.order_part_log import OrderPartLogCreate, OrderPartLogResponse
from app.dao.order_part_log import order_part_log_dao


router = APIRouter()


@router.get("/", response_model=List[OrderPartLogResponse])
def get_order_part_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=100),
    order_part_id: int = Query(None),
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Get all order part logs, optionally filtered by order part"""
    if order_part_id:
        logs = order_part_log_dao.get_by_order_part(db, order_part_id=order_part_id, skip=skip, limit=limit)
    else:
        logs = order_part_log_dao.get_multi(db, skip=skip, limit=limit)
    return logs


@router.get("/{log_id}", response_model=OrderPartLogResponse)
def get_order_part_log(
    log_id: int,
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Get order part log by ID"""
    log = order_part_log_dao.get(db, id=log_id)
    if not log:
        raise HTTPException(status_code=404, detail="Order part log not found")
    return log


@router.post("/", response_model=OrderPartLogResponse, status_code=201)
def create_order_part_log(
    log_in: OrderPartLogCreate,
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Create new order part log (audit entry)"""
    log = order_part_log_dao.create(db, obj_in=log_in)
    return log
