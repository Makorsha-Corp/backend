"""Status endpoints"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_active_user
from app.models.profile import Profile
from app.schemas.status import StatusCreate, StatusUpdate, StatusResponse
from app.dao.status import status_dao


router = APIRouter()


@router.get("/", response_model=List[StatusResponse])
def get_statuses(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=100),
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Get all statuses"""
    statuses = status_dao.get_multi(db, skip=skip, limit=limit)
    return statuses


@router.get("/{status_id}", response_model=StatusResponse)
def get_status(
    status_id: int,
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Get status by ID"""
    status = status_dao.get(db, id=status_id)
    if not status:
        raise HTTPException(status_code=404, detail="Status not found")
    return status


@router.post("/", response_model=StatusResponse, status_code=201)
def create_status(
    status_in: StatusCreate,
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Create new status"""
    status = status_dao.create(db, obj_in=status_in)
    return status


@router.put("/{status_id}", response_model=StatusResponse)
def update_status(
    status_id: int,
    status_in: StatusUpdate,
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Update status"""
    status = status_dao.get(db, id=status_id)
    if not status:
        raise HTTPException(status_code=404, detail="Status not found")
    status = status_dao.update(db, db_obj=status, obj_in=status_in)
    return status


@router.delete("/{status_id}", status_code=204)
def delete_status(
    status_id: int,
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Delete status"""
    status = status_dao.get(db, id=status_id)
    if not status:
        raise HTTPException(status_code=404, detail="Status not found")
    status_dao.remove(db, id=status_id)
