"""App settings endpoints"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_active_user
from app.models.profile import Profile
from app.schemas.app_settings import AppSettingsCreate, AppSettingsUpdate, AppSettingsResponse
from app.dao.app_settings import app_settings_dao


router = APIRouter()


@router.get("/", response_model=List[AppSettingsResponse])
def get_app_settings(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=100),
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Get all app settings"""
    settings = app_settings_dao.get_multi(db, skip=skip, limit=limit)
    return settings


@router.get("/{setting_id}", response_model=AppSettingsResponse)
def get_app_setting(
    setting_id: int,
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Get app setting by ID"""
    setting = app_settings_dao.get(db, id=setting_id)
    if not setting:
        raise HTTPException(status_code=404, detail="App setting not found")
    return setting


@router.get("/name/{name}", response_model=AppSettingsResponse)
def get_app_setting_by_name(
    name: str,
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Get app setting by name"""
    setting = app_settings_dao.get_by_name(db, name=name)
    if not setting:
        raise HTTPException(status_code=404, detail="App setting not found")
    return setting


@router.post("/", response_model=AppSettingsResponse, status_code=201)
def create_app_setting(
    setting_in: AppSettingsCreate,
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Create new app setting"""
    setting = app_settings_dao.create(db, obj_in=setting_in)
    return setting


@router.put("/{setting_id}", response_model=AppSettingsResponse)
def update_app_setting(
    setting_id: int,
    setting_in: AppSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Update app setting"""
    setting = app_settings_dao.get(db, id=setting_id)
    if not setting:
        raise HTTPException(status_code=404, detail="App setting not found")
    setting = app_settings_dao.update(db, db_obj=setting, obj_in=setting_in)
    return setting


@router.delete("/{setting_id}", status_code=204)
def delete_app_setting(
    setting_id: int,
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_active_user)
):
    """Delete app setting"""
    setting = app_settings_dao.get(db, id=setting_id)
    if not setting:
        raise HTTPException(status_code=404, detail="App setting not found")
    app_settings_dao.remove(db, id=setting_id)
