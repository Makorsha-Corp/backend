"""Order part log endpoints"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_active_user, get_current_workspace
from app.models.profile import Profile
from app.models.workspace import Workspace
from app.schemas.order_part_log import OrderPartLogCreate, OrderPartLogResponse
from app.services.order_part_log_service import order_part_log_service


router = APIRouter()


@router.get("/", response_model=List[OrderPartLogResponse])
def get_order_part_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=100),
    order_part_id: int = Query(None),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Get all order part logs, optionally filtered by order part"""
    return order_part_log_service.get_logs(db, workspace_id=workspace.id, order_part_id=order_part_id, skip=skip, limit=limit)


@router.get("/{log_id}/", response_model=OrderPartLogResponse)
def get_order_part_log(
    log_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Get order part log by ID"""
    log = order_part_log_service.get_by_id(db, log_id=log_id, workspace_id=workspace.id)
    if not log:
        raise HTTPException(status_code=404, detail="Order part log not found")
    return log


@router.post("/", response_model=OrderPartLogResponse, status_code=201)
def create_order_part_log(
    log_in: OrderPartLogCreate,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Create new order part log (audit entry)"""
    return order_part_log_service.create_log(db, log_in=log_in, workspace_id=workspace.id)
