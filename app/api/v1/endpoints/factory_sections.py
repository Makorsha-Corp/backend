"""
Factory Section API endpoints

Provides operations for managing factory sections (areas within factories).
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_workspace, get_current_active_user
from app.models.workspace import Workspace
from app.models.profile import Profile
from app.schemas.factory_section import FactorySectionCreate, FactorySectionUpdate, FactorySectionResponse
from app.services.factory_section_service import factory_section_service


router = APIRouter()


@router.get(
    "/",
    response_model=List[FactorySectionResponse],
    status_code=status.HTTP_200_OK,
    summary="List all factory sections",
    description="Get all factory sections in the workspace, optionally filtered by factory"
)
def get_factory_sections(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    factory_id: Optional[int] = Query(None, description="Filter by factory ID"),
    search: Optional[str] = Query(None, description="Search by name"),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Get all factory sections in workspace"""
    sections = factory_section_service.get_factory_sections(
        db,
        workspace_id=workspace.id,
        factory_id=factory_id,
        search=search,
        skip=skip,
        limit=limit
    )
    return sections


@router.get(
    "/{section_id}",
    response_model=FactorySectionResponse,
    status_code=status.HTTP_200_OK,
    summary="Get factory section by ID",
    description="Get a specific factory section by ID"
)
def get_factory_section(
    section_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Get a specific factory section"""
    section = factory_section_service.get_factory_section(
        db,
        section_id=section_id,
        workspace_id=workspace.id
    )
    return section


@router.post(
    "/",
    response_model=FactorySectionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new factory section",
    description="Create a new factory section (must belong to a factory)"
)
def create_factory_section(
    section_in: FactorySectionCreate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new factory section"""
    section = factory_section_service.create_factory_section(
        db,
        section_in=section_in,
        workspace_id=workspace.id,
        user_id=current_user.id
    )
    return section


@router.put(
    "/{section_id}",
    response_model=FactorySectionResponse,
    status_code=status.HTTP_200_OK,
    summary="Update factory section",
    description="Update an existing factory section"
)
def update_factory_section(
    section_id: int,
    section_in: FactorySectionUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update a factory section"""
    section = factory_section_service.update_factory_section(
        db,
        section_id=section_id,
        section_in=section_in,
        workspace_id=workspace.id,
        user_id=current_user.id
    )
    return section


@router.delete(
    "/{section_id}",
    response_model=FactorySectionResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete factory section",
    description="Soft delete a factory section"
)
def delete_factory_section(
    section_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Soft delete a factory section"""
    section = factory_section_service.delete_factory_section(
        db,
        section_id=section_id,
        workspace_id=workspace.id,
        user_id=current_user.id
    )
    return section
