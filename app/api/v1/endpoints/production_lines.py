"""
Production Line endpoints

Provides CRUD operations for production lines.
Production lines represent physical production locations that can be
attached to machines or standalone.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_active_user, get_current_workspace
from app.models.profile import Profile
from app.models.workspace import Workspace
from app.schemas.production_line import (
    ProductionLineCreate,
    ProductionLineUpdate,
    ProductionLineResponse,
)
from app.services.production_line_service import production_line_service


router = APIRouter()


@router.get(
    "/",
    response_model=List[ProductionLineResponse],
    status_code=status.HTTP_200_OK,
    summary="List production lines",
    description="""
    Get all production lines with optional filtering by factory and active status.
    Supports pagination with skip/limit.
    """
)
def get_production_lines(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, le=100, description="Maximum number of records to return"),
    factory_id: Optional[int] = Query(None, description="Filter by factory ID"),
    active_only: bool = Query(False, description="Only return active production lines"),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    """Get all production lines with optional filters"""
    lines = production_line_service.get_production_lines(
        db,
        workspace_id=workspace.id,
        factory_id=factory_id,
        active_only=active_only,
        skip=skip,
        limit=limit,
    )
    return lines


@router.get(
    "/{line_id}",
    response_model=ProductionLineResponse,
    status_code=status.HTTP_200_OK,
    summary="Get production line by ID",
    description="Retrieve a single production line by its ID. Raises 404 if not found.",
)
def get_production_line(
    line_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    """Get production line by ID"""
    line = production_line_service.get_production_line(
        db, line_id, workspace_id=workspace.id
    )
    return line


@router.post(
    "/",
    response_model=ProductionLineResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create production line",
    description="""
    Create a new production line. Requires a factory_id.
    Optionally attach to a machine via machine_id.
    Machine must belong to the specified factory.
    """,
)
def create_production_line(
    line_in: ProductionLineCreate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Create new production line"""
    line = production_line_service.create_production_line(
        db, line_in, workspace.id, current_user.id
    )
    return line


@router.put(
    "/{line_id}",
    response_model=ProductionLineResponse,
    status_code=status.HTTP_200_OK,
    summary="Update production line",
    description="Update an existing production line. Returns the updated production line.",
)
def update_production_line(
    line_id: int,
    line_in: ProductionLineUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Update production line"""
    line = production_line_service.update_production_line(
        db, line_id, line_in, workspace.id, current_user.id
    )
    return line


@router.delete(
    "/{line_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete production line",
    description="Soft delete a production line (sets is_active=False). Returns 204 No Content on success.",
)
def delete_production_line(
    line_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Delete production line (soft delete)"""
    production_line_service.delete_production_line(db, line_id, workspace.id)
