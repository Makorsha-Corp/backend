"""
Department API endpoints

Provides operations for managing departments (organizational units).
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_active_user, get_current_workspace
from app.models.profile import Profile
from app.models.workspace import Workspace
from app.schemas.department import DepartmentCreate, DepartmentUpdate, DepartmentResponse
from app.services.department_service import department_service


router = APIRouter()


@router.get(
    "/",
    response_model=List[DepartmentResponse],
    status_code=status.HTTP_200_OK,
    summary="List all departments",
    description="Get all departments in the workspace with optional search"
)
def get_departments(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: Optional[str] = Query(None, description="Search by name"),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Get all departments in workspace"""
    departments = department_service.get_departments(
        db,
        workspace_id=workspace.id,
        search=search,
        skip=skip,
        limit=limit
    )
    return departments


@router.get(
    "/{department_id}",
    response_model=DepartmentResponse,
    status_code=status.HTTP_200_OK,
    summary="Get department by ID",
    description="Get a specific department by ID"
)
def get_department(
    department_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Get a specific department"""
    department = department_service.get_department(
        db,
        department_id=department_id,
        workspace_id=workspace.id
    )
    return department


@router.post(
    "/",
    response_model=DepartmentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new department",
    description="Create a new department"
)
def create_department(
    department_in: DepartmentCreate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new department"""
    department = department_service.create_department(
        db,
        department_in=department_in,
        workspace_id=workspace.id,
        user_id=current_user.id
    )
    return department


@router.put(
    "/{department_id}",
    response_model=DepartmentResponse,
    status_code=status.HTTP_200_OK,
    summary="Update department",
    description="Update an existing department"
)
def update_department(
    department_id: int,
    department_in: DepartmentUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update a department"""
    department = department_service.update_department(
        db,
        department_id=department_id,
        department_in=department_in,
        workspace_id=workspace.id,
        user_id=current_user.id
    )
    return department


@router.delete(
    "/{department_id}",
    response_model=DepartmentResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete department",
    description="Soft delete a department"
)
def delete_department(
    department_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Soft delete a department"""
    department = department_service.delete_department(
        db,
        department_id=department_id,
        workspace_id=workspace.id,
        user_id=current_user.id
    )
    return department
