"""Damaged item endpoints"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_active_user, get_current_workspace
from app.models.profile import Profile
from app.models.workspace import Workspace
from app.schemas.damaged_item import DamagedItemCreate, DamagedItemUpdate, DamagedItemResponse
from app.services.damaged_item_service import damaged_item_service


router = APIRouter()


@router.get("/", response_model=List[DamagedItemResponse])
def get_damaged_items(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=100),
    factory_id: int = Query(None),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Get all damaged items, optionally filtered by factory"""
    return damaged_item_service.get_items(db, workspace_id=workspace.id, factory_id=factory_id, skip=skip, limit=limit)


@router.get("/{damaged_item_id}/", response_model=DamagedItemResponse)
def get_damaged_part(
    damaged_item_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Get damaged item by ID"""
    item = damaged_item_service.get_by_id(db, item_id=damaged_item_id, workspace_id=workspace.id)
    if not item:
        raise HTTPException(status_code=404, detail="Damaged item not found")
    return item


@router.post("/", response_model=DamagedItemResponse, status_code=201)
def create_damaged_item(
    item_in: DamagedItemCreate,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Create new damaged item"""
    return damaged_item_service.create_item(db, item_in=item_in, workspace_id=workspace.id)


@router.put("/{damaged_item_id}/", response_model=DamagedItemResponse)
def update_damaged_item(
    damaged_item_id: int,
    item_in: DamagedItemUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Update damaged item"""
    item = damaged_item_service.update_item(db, item_id=damaged_item_id, item_in=item_in, workspace_id=workspace.id)
    if not item:
        raise HTTPException(status_code=404, detail="Damaged item not found")
    return item


@router.delete("/{damaged_item_id}/", status_code=204)
def delete_damaged_item(
    damaged_item_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Delete damaged item"""
    deleted = damaged_item_service.delete_item(db, item_id=damaged_item_id, workspace_id=workspace.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Damaged item not found")
