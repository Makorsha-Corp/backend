"""
Machine maintenance log API endpoints

Provides operations for managing machine maintenance logs.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_workspace, get_current_active_user
from app.models.workspace import Workspace
from app.models.profile import Profile
from app.models.enums import MaintenanceTypeEnum
from app.schemas.machine_maintenance_log import (
    MachineMaintenanceLogCreate,
    MachineMaintenanceLogUpdate,
    MachineMaintenanceLogResponse,
)
from app.services.machine_maintenance_log_service import machine_maintenance_log_service


router = APIRouter()


@router.get(
    "/",
    response_model=List[MachineMaintenanceLogResponse],
    status_code=status.HTTP_200_OK,
    summary="List maintenance logs",
    description="Get all maintenance logs, optionally filtered by machine or type"
)
def list_maintenance_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    machine_id: Optional[int] = Query(None, description="Filter by machine ID"),
    maintenance_type: Optional[MaintenanceTypeEnum] = Query(None, description="Filter by maintenance type"),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Get all maintenance logs in workspace"""
    return machine_maintenance_log_service.list_logs(
        db, workspace_id=workspace.id,
        machine_id=machine_id, maintenance_type=maintenance_type,
        skip=skip, limit=limit
    )


@router.get(
    "/{log_id}/",
    response_model=MachineMaintenanceLogResponse,
    status_code=status.HTTP_200_OK,
    summary="Get maintenance log by ID"
)
def get_maintenance_log(
    log_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Get a specific maintenance log"""
    return machine_maintenance_log_service.get_log(
        db, log_id=log_id, workspace_id=workspace.id
    )


@router.post(
    "/",
    response_model=MachineMaintenanceLogResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create maintenance log"
)
def create_maintenance_log(
    log_in: MachineMaintenanceLogCreate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new maintenance log entry"""
    return machine_maintenance_log_service.create_log(
        db, log_in=log_in,
        workspace_id=workspace.id, user_id=current_user.id
    )


@router.put(
    "/{log_id}/",
    response_model=MachineMaintenanceLogResponse,
    status_code=status.HTTP_200_OK,
    summary="Update maintenance log"
)
def update_maintenance_log(
    log_id: int,
    log_in: MachineMaintenanceLogUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update a maintenance log entry"""
    return machine_maintenance_log_service.update_log(
        db, log_id=log_id, log_in=log_in,
        workspace_id=workspace.id, user_id=current_user.id
    )


@router.delete(
    "/{log_id}/",
    response_model=MachineMaintenanceLogResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete maintenance log"
)
def delete_maintenance_log(
    log_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Soft delete a maintenance log"""
    return machine_maintenance_log_service.delete_log(
        db, log_id=log_id,
        workspace_id=workspace.id, user_id=current_user.id
    )
