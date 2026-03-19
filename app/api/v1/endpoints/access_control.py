"""Access control endpoints"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_active_user
from app.models.profile import Profile
from app.models.enums import RoleEnum, AccessControlTypeEnum
from app.schemas.access_control import AccessControlCreate, AccessControlUpdate, AccessControlResponse
from app.dao.access_control import access_control_dao


router = APIRouter()


@router.get("/", response_model=List[AccessControlResponse])
def get_access_controls(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=100),
    role: RoleEnum = Query(None),
    access_type: AccessControlTypeEnum = Query(None),
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Get all access controls, optionally filtered by role or type"""
    if role:
        controls = access_control_dao.get_by_role(db, role=role, skip=skip, limit=limit)
    elif access_type:
        controls = access_control_dao.get_by_type(db, access_type=access_type, skip=skip, limit=limit)
    else:
        controls = access_control_dao.get_multi(db, skip=skip, limit=limit)
    return controls


@router.get("/{control_id}", response_model=AccessControlResponse)
def get_access_control(
    control_id: int,
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Get access control by ID"""
    control = access_control_dao.get(db, id=control_id)
    if not control:
        raise HTTPException(status_code=404, detail="Access control not found")
    return control


@router.post("/", response_model=AccessControlResponse, status_code=201)
def create_access_control(
    control_in: AccessControlCreate,
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Create new access control"""
    control = access_control_dao.create(db, obj_in=control_in)
    return control


@router.put("/{control_id}", response_model=AccessControlResponse)
def update_access_control(
    control_id: int,
    control_in: AccessControlUpdate,
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Update access control"""
    control = access_control_dao.get(db, id=control_id)
    if not control:
        raise HTTPException(status_code=404, detail="Access control not found")
    control = access_control_dao.update(db, db_obj=control, obj_in=control_in)
    return control


@router.delete("/{control_id}", status_code=204)
def delete_access_control(
    control_id: int,
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Delete access control"""
    control = access_control_dao.get(db, id=control_id)
    if not control:
        raise HTTPException(status_code=404, detail="Access control not found")
    access_control_dao.remove(db, id=control_id)
