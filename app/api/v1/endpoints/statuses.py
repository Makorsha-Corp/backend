"""Status endpoints"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_active_user
from app.models.profile import Profile
from app.schemas.status import StatusCreate, StatusUpdate, StatusResponse
from app.services.status_service import status_service


router = APIRouter()


@router.get("/", response_model=List[StatusResponse])
def get_statuses(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=100),
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Get all statuses"""
    return status_service.get_statuses(db, skip=skip, limit=limit)


@router.get("/{status_id}/", response_model=StatusResponse)
def get_status(
    status_id: int,
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Get status by ID"""
    status = status_service.get_by_id(db, status_id=status_id)
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
    return status_service.create_status(db, status_in=status_in)


@router.put("/{status_id}/", response_model=StatusResponse)
def update_status(
    status_id: int,
    status_in: StatusUpdate,
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Update status"""
    status = status_service.update_status(db, status_id=status_id, status_in=status_in)
    if not status:
        raise HTTPException(status_code=404, detail="Status not found")
    return status


@router.delete("/{status_id}/", status_code=204)
def delete_status(
    status_id: int,
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Delete status"""
    deleted = status_service.delete_status(db, status_id=status_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Status not found")
