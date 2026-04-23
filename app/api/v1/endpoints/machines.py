"""
Machine API endpoints

Provides operations for managing machines and machine events (status changes).
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_workspace, get_current_active_user
from app.models.workspace import Workspace
from app.models.profile import Profile
from app.models.enums import MachineEventTypeEnum
from app.schemas.machine import MachineCreate, MachineUpdate, MachineResponse
from app.schemas.machine_event import MachineEventCreate, MachineEventResponse
from app.services.machine_service import machine_service


router = APIRouter()


# ==================== MACHINE CRUD ====================

@router.get(
    "/",
    response_model=List[MachineResponse],
    status_code=status.HTTP_200_OK,
    summary="List all machines",
    description="Get all machines in the workspace, optionally filtered"
)
def get_machines(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    factory_section_id: Optional[int] = Query(None, description="Filter by factory section ID"),
    is_running: Optional[bool] = Query(None, description="Filter by running status"),
    search: Optional[str] = Query(None, description="Search by name, model_number, or manufacturer"),
    maintenance_window: str = Query(
        "all",
        description="Maintenance filter: all | overdue | next_7_days | next_30_days | none_scheduled"
    ),
    has_model_number: Optional[bool] = Query(None, description="Filter by model number presence"),
    has_manufacturer: Optional[bool] = Query(None, description="Filter by manufacturer presence"),
    latest_event_type: Optional[MachineEventTypeEnum] = Query(None, description="Filter by latest machine event type"),
    sort_by: str = Query("name", description="Sort field: name | created_at | maintenance_date"),
    sort_dir: str = Query("asc", description="Sort direction: asc | desc"),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Get all machines in workspace"""
    return machine_service.get_machines(
        db, workspace_id=workspace.id,
        factory_section_id=factory_section_id,
        is_running=is_running, search=search,
        maintenance_window=maintenance_window,
        has_model_number=has_model_number,
        has_manufacturer=has_manufacturer,
        latest_event_type=latest_event_type,
        sort_by=sort_by,
        sort_dir=sort_dir,
        skip=skip, limit=limit
    )


@router.get(
    "/{machine_id}/",
    response_model=MachineResponse,
    status_code=status.HTTP_200_OK,
    summary="Get machine by ID"
)
def get_machine(
    machine_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Get a specific machine"""
    return machine_service.get_machine(db, machine_id=machine_id, workspace_id=workspace.id)


@router.post(
    "/",
    response_model=MachineResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new machine"
)
def create_machine(
    machine_in: MachineCreate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new machine"""
    return machine_service.create_machine(
        db, machine_in=machine_in,
        workspace_id=workspace.id, user_id=current_user.id
    )


@router.put(
    "/{machine_id}/",
    response_model=MachineResponse,
    status_code=status.HTTP_200_OK,
    summary="Update machine"
)
def update_machine(
    machine_id: int,
    machine_in: MachineUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update machine metadata (does not change running status -- use events)"""
    return machine_service.update_machine(
        db, machine_id=machine_id, machine_in=machine_in,
        workspace_id=workspace.id, user_id=current_user.id
    )


@router.delete(
    "/{machine_id}/",
    response_model=MachineResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete machine"
)
def delete_machine(
    machine_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Soft delete a machine"""
    return machine_service.delete_machine(
        db, machine_id=machine_id,
        workspace_id=workspace.id, user_id=current_user.id
    )


# ==================== MACHINE EVENTS ====================

@router.post(
    "/{machine_id}/events/",
    response_model=MachineEventResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create machine event",
    description="Record a machine status change event. Automatically syncs machine.is_running."
)
def create_machine_event(
    machine_id: int,
    event_in: MachineEventCreate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a machine event (status change)"""
    # Override machine_id from path parameter for consistency
    event_in.machine_id = machine_id
    return machine_service.create_machine_event(
        db, event_in=event_in,
        workspace_id=workspace.id, user_id=current_user.id
    )


@router.get(
    "/{machine_id}/events/",
    response_model=List[MachineEventResponse],
    status_code=status.HTTP_200_OK,
    summary="Get machine events",
    description="Get status change history for a machine"
)
def get_machine_events(
    machine_id: int,
    event_type: Optional[MachineEventTypeEnum] = Query(None, description="Filter by event type"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Get events for a specific machine"""
    return machine_service.get_machine_events(
        db, machine_id=machine_id,
        workspace_id=workspace.id, event_type=event_type,
        skip=skip, limit=limit
    )


@router.get(
    "/{machine_id}/events/latest/",
    response_model=MachineEventResponse,
    status_code=status.HTTP_200_OK,
    summary="Get latest machine event"
)
def get_latest_machine_event(
    machine_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Get the most recent event for a machine"""
    event = machine_service.get_latest_machine_event(
        db, machine_id=machine_id, workspace_id=workspace.id
    )
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No events found for machine with ID {machine_id}"
        )
    return event
