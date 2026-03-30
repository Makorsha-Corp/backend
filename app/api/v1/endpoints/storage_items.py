"""Storage item endpoints"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_active_user, get_current_workspace
from app.models.profile import Profile
from app.models.workspace import Workspace
from app.schemas.storage_item import StorageItemCreate, StorageItemUpdate, StorageItemResponse
from app.services.storage_item_service import storage_item_service


router = APIRouter()


@router.get("/", response_model=List[StorageItemResponse])
def get_storage_items(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=100),
    factory_id: int = Query(None),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Get all storage items, optionally filtered by factory"""
    return storage_item_service.get_items(db, workspace_id=workspace.id, factory_id=factory_id, skip=skip, limit=limit)


@router.get("/{storage_item_id}/", response_model=StorageItemResponse)
def get_storage_item(
    storage_item_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Get storage item by ID"""
    item = storage_item_service.get_by_id(db, item_id=storage_item_id, workspace_id=workspace.id)
    if not item:
        raise HTTPException(status_code=404, detail="Storage item not found")
    return item


@router.post("/", response_model=StorageItemResponse, status_code=201)
def create_storage_item(
    item_in: StorageItemCreate,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Create new storage item"""
    return storage_item_service.create_item(db, item_in=item_in, workspace_id=workspace.id)


@router.put("/{storage_item_id}/", response_model=StorageItemResponse)
def update_storage_item(
    storage_item_id: int,
    item_in: StorageItemUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Update storage item"""
    item = storage_item_service.update_item(db, item_id=storage_item_id, item_in=item_in, workspace_id=workspace.id)
    if not item:
        raise HTTPException(status_code=404, detail="Storage item not found")
    return item


@router.delete("/{storage_item_id}/", status_code=204)
def delete_storage_item(
    storage_item_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Delete storage item"""
    deleted = storage_item_service.delete_item(db, item_id=storage_item_id, workspace_id=workspace.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Storage item not found")
