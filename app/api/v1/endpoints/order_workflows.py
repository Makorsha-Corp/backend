"""Order workflow endpoints"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_active_user
from app.models.profile import Profile
from app.schemas.order_workflow import OrderWorkflowCreate, OrderWorkflowUpdate, OrderWorkflowResponse
from app.dao.order_workflow import order_workflow_dao


router = APIRouter()


@router.get("/", response_model=List[OrderWorkflowResponse])
def get_order_workflows(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=100),
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Get all order workflows"""
    workflows = order_workflow_dao.get_multi(db, skip=skip, limit=limit)
    return workflows


@router.get("/{workflow_id}", response_model=OrderWorkflowResponse)
def get_order_workflow(
    workflow_id: int,
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Get order workflow by ID"""
    workflow = order_workflow_dao.get(db, id=workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Order workflow not found")
    return workflow


@router.get("/type/{workflow_type}", response_model=OrderWorkflowResponse)
def get_order_workflow_by_type(
    workflow_type: str,
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Get order workflow by type (PFM, PFS, STM, etc.)"""
    workflow = order_workflow_dao.get_by_type(db, workflow_type=workflow_type)
    if not workflow:
        raise HTTPException(status_code=404, detail="Order workflow not found")
    return workflow


@router.post("/", response_model=OrderWorkflowResponse, status_code=201)
def create_order_workflow(
    workflow_in: OrderWorkflowCreate,
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Create new order workflow"""
    workflow = order_workflow_dao.create(db, obj_in=workflow_in)
    return workflow


@router.put("/{workflow_id}", response_model=OrderWorkflowResponse)
def update_order_workflow(
    workflow_id: int,
    workflow_in: OrderWorkflowUpdate,
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Update order workflow"""
    workflow = order_workflow_dao.get(db, id=workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Order workflow not found")
    workflow = order_workflow_dao.update(db, db_obj=workflow, obj_in=workflow_in)
    return workflow


@router.delete("/{workflow_id}", status_code=204)
def delete_order_workflow(
    workflow_id: int,
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Delete order workflow"""
    workflow = order_workflow_dao.get(db, id=workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Order workflow not found")
    order_workflow_dao.remove(db, id=workflow_id)
