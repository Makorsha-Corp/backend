"""Storage item endpoints"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_active_user
from app.models.profile import Profile
from app.schemas.storage_item import StorageItemCreate, StorageItemUpdate, StorageItemResponse
from app.dao.storage_item import storage_item_dao


router = APIRouter()


@router.get("/", response_model=List[StorageItemResponse])  
def get_storage_items(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=100),
    factory_id: int = Query(None),
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Get all storage items, optionally filtered by factory"""
    if factory_id:
        items = storage_item_dao.get_by_factory(db, factory_id=factory_id, skip=skip, limit=limit)
    else:
        items = storage_item_dao.get_multi(db, skip=skip, limit=limit)
    return items


@router.get("/{storage_item_id}", response_model=StorageItemResponse)
def get_storage_item(
    storage_item_id: int,
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Get storage item by ID"""
    item = storage_item_dao.get(db, id=storage_item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Storage item not found")
    return item


@router.post("/", response_model=StorageItemResponse, status_code=201)
def create_storage_item(
    item_in: StorageItemCreate,
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Create new storage item"""
    item = storage_item_dao.create(db, obj_in=item_in)
    return item


@router.put("/{storage_item_id}", response_model=StorageItemResponse)
def update_storage_item(
    storage_item_id: int,
    item_in: StorageItemUpdate,
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Update storage item"""
    item = storage_item_dao.get(db, id=storage_item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Storage item not found")
    item = storage_item_dao.update(db, db_obj=item, obj_in=item_in)
    return item


@router.delete("/{storage_item_id}", status_code=204)
def delete_storage_item(
    storage_item_id: int,
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Delete storage item"""
    item = storage_item_dao.get(db, id=storage_item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Storage item not found")
    storage_item_dao.remove(db, id=storage_item_id)
