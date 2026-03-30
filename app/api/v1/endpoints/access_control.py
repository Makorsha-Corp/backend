"""Access control endpoints"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_active_user, get_current_workspace
from app.models.profile import Profile
from app.models.workspace import Workspace
from app.models.enums import RoleEnum, AccessControlTypeEnum
from app.schemas.access_control import AccessControlCreate, AccessControlUpdate, AccessControlResponse
from app.services.access_control_service import access_control_service


router = APIRouter()


@router.get("/", response_model=List[AccessControlResponse])
def get_access_controls(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=100),
    role: RoleEnum = Query(None),
    access_type: AccessControlTypeEnum = Query(None),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Get all access controls, optionally filtered by role or type"""
    return access_control_service.get_controls(db, workspace_id=workspace.id, role=role, access_type=access_type, skip=skip, limit=limit)


@router.get("/{control_id}/", response_model=AccessControlResponse)
def get_access_control(
    control_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Get access control by ID"""
    control = access_control_service.get_by_id(db, control_id=control_id, workspace_id=workspace.id)
    if not control:
        raise HTTPException(status_code=404, detail="Access control not found")
    return control


@router.post("/", response_model=AccessControlResponse, status_code=201)
def create_access_control(
    control_in: AccessControlCreate,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Create new access control"""
    return access_control_service.create_control(db, control_in=control_in, workspace_id=workspace.id)


@router.put("/{control_id}/", response_model=AccessControlResponse)
def update_access_control(
    control_id: int,
    control_in: AccessControlUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Update access control"""
    control = access_control_service.update_control(db, control_id=control_id, control_in=control_in, workspace_id=workspace.id)
    if not control:
        raise HTTPException(status_code=404, detail="Access control not found")
    return control


@router.delete("/{control_id}/", status_code=204)
def delete_access_control(
    control_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Delete access control"""
    deleted = access_control_service.delete_control(db, control_id=control_id, workspace_id=workspace.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Access control not found")
