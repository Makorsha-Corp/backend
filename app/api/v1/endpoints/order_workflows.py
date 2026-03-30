"""Order workflow endpoints"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_active_user, get_current_workspace
from app.models.profile import Profile
from app.models.workspace import Workspace
from app.schemas.order_workflow import OrderWorkflowCreate, OrderWorkflowUpdate, OrderWorkflowResponse
from app.services.order_workflow_service import order_workflow_service


router = APIRouter()


@router.get("/", response_model=List[OrderWorkflowResponse])
def get_order_workflows(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=100),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Get all order workflows"""
    return order_workflow_service.get_workflows(db, workspace_id=workspace.id, skip=skip, limit=limit)


@router.get("/{workflow_id}/", response_model=OrderWorkflowResponse)
def get_order_workflow(
    workflow_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Get order workflow by ID"""
    workflow = order_workflow_service.get_by_id(db, workflow_id=workflow_id, workspace_id=workspace.id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Order workflow not found")
    return workflow


@router.get("/type/{workflow_type}/", response_model=OrderWorkflowResponse)
def get_order_workflow_by_type(
    workflow_type: str,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Get order workflow by type (PFM, PFS, STM, etc.)"""
    workflow = order_workflow_service.get_by_type(db, workflow_type=workflow_type, workspace_id=workspace.id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Order workflow not found")
    return workflow


@router.post("/", response_model=OrderWorkflowResponse, status_code=201)
def create_order_workflow(
    workflow_in: OrderWorkflowCreate,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Create new order workflow"""
    return order_workflow_service.create_workflow(db, workflow_in=workflow_in, workspace_id=workspace.id)


@router.put("/{workflow_id}/", response_model=OrderWorkflowResponse)
def update_order_workflow(
    workflow_id: int,
    workflow_in: OrderWorkflowUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Update order workflow"""
    workflow = order_workflow_service.update_workflow(db, workflow_id=workflow_id, workflow_in=workflow_in, workspace_id=workspace.id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Order workflow not found")
    return workflow


@router.delete("/{workflow_id}/", status_code=204)
def delete_order_workflow(
    workflow_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Delete order workflow"""
    deleted = order_workflow_service.delete_workflow(db, workflow_id=workflow_id, workspace_id=workspace.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Order workflow not found")
