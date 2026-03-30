"""App settings endpoints"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_active_user, get_current_workspace
from app.models.profile import Profile
from app.models.workspace import Workspace
from app.schemas.app_settings import AppSettingsCreate, AppSettingsUpdate, AppSettingsResponse
from app.services.app_settings_service import app_settings_service


router = APIRouter()


@router.get("/", response_model=List[AppSettingsResponse])
def get_app_settings(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=100),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Get all app settings"""
    return app_settings_service.get_settings(db, workspace_id=workspace.id, skip=skip, limit=limit)


@router.get("/{setting_id}/", response_model=AppSettingsResponse)
def get_app_setting(
    setting_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Get app setting by ID"""
    setting = app_settings_service.get_by_id(db, setting_id=setting_id, workspace_id=workspace.id)
    if not setting:
        raise HTTPException(status_code=404, detail="App setting not found")
    return setting


@router.get("/name/{name}/", response_model=AppSettingsResponse)
def get_app_setting_by_name(
    name: str,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Get app setting by name"""
    setting = app_settings_service.get_by_name(db, name=name, workspace_id=workspace.id)
    if not setting:
        raise HTTPException(status_code=404, detail="App setting not found")
    return setting


@router.post("/", response_model=AppSettingsResponse, status_code=201)
def create_app_setting(
    setting_in: AppSettingsCreate,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Create new app setting"""
    return app_settings_service.create_setting(db, setting_in=setting_in, workspace_id=workspace.id)


@router.put("/{setting_id}/", response_model=AppSettingsResponse)
def update_app_setting(
    setting_id: int,
    setting_in: AppSettingsUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Update app setting"""
    setting = app_settings_service.update_setting(db, setting_id=setting_id, setting_in=setting_in, workspace_id=workspace.id)
    if not setting:
        raise HTTPException(status_code=404, detail="App setting not found")
    return setting


@router.delete("/{setting_id}/", status_code=204)
def delete_app_setting(
    setting_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Delete app setting"""
    deleted = app_settings_service.delete_setting(db, setting_id=setting_id, workspace_id=workspace.id)
    if not deleted:
        raise HTTPException(status_code=404, detail="App setting not found")
