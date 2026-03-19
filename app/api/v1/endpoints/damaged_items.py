"""Damaged item endpoints"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_active_user
from app.models.profile import Profile
from app.schemas.damaged_item import DamagedItemCreate, DamagedItemUpdate, DamagedItemResponse
from app.dao.damaged_item import damaged_item_dao


router = APIRouter()


@router.get("/", response_model=List[DamagedItemResponse])
def get_damaged_items(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=100),
    factory_id: int = Query(None),
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Get all damaged items, optionally filtered by factory"""
    if factory_id:
        items = damaged_item_dao.get_by_factory(db, factory_id=factory_id, skip=skip, limit=limit)
    else:
        items = damaged_item_dao.get_multi(db, skip=skip, limit=limit)
    return items


@router.get("/{damaged_item_id}", response_model=DamagedItemResponse)
def get_damaged_part(
    damaged_item_id: int,
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Get damaged item by ID"""
    item = damaged_item_dao.get(db, id=damaged_item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Damaged item not found")
    return item


@router.post("/", response_model=DamagedItemResponse, status_code=201)
def create_damaged_item(
    item_in: DamagedItemCreate,
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Create new damaged item"""
    item = damaged_item_dao.create(db, obj_in=item_in)
    return item


@router.put("/{damaged_item_id}", response_model=DamagedItemResponse)
def update_damaged_item(
    damaged_item_id: int,
    item_in: DamagedItemUpdate,
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Update damaged item"""
    item = damaged_item_dao.get(db, id=damaged_item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Damaged item not found")
    item = damaged_item_dao.update(db, db_obj=item, obj_in=item_in)
    return item


@router.delete("/{damaged_item_id}", status_code=204)
def delete_damaged_item(
    damaged_item_id: int,
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Delete damaged item"""
    item = damaged_item_dao.get(db, id=damaged_item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Damaged item not found")
    damaged_item_dao.remove(db, id=damaged_item_id)
