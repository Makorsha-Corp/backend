"""
Factory API endpoints

Provides operations for managing factory locations.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_workspace, get_current_active_user
from app.models.workspace import Workspace
from app.models.profile import Profile
from app.schemas.factory import FactoryCreate, FactoryUpdate, FactoryResponse
from app.services.factory_service import factory_service


router = APIRouter()


@router.get(
    "/",
    response_model=List[FactoryResponse],
    status_code=status.HTTP_200_OK,
    summary="List all factories",
    description="Get all factories in the workspace with optional search"
)
def get_factories(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: Optional[str] = Query(None, description="Search by name or abbreviation"),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Get all factories in workspace"""
    factories = factory_service.get_factories(
        db,
        workspace_id=workspace.id,
        search=search,
        skip=skip,
        limit=limit
    )
    return factories


@router.get(
    "/{factory_id}",
    response_model=FactoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get factory by ID",
    description="Get a specific factory by ID"
)
def get_factory(
    factory_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Get a specific factory"""
    factory = factory_service.get_factory(
        db,
        factory_id=factory_id,
        workspace_id=workspace.id
    )
    return factory


@router.post(
    "/",
    response_model=FactoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new factory",
    description="Create a new factory location"
)
def create_factory(
    factory_in: FactoryCreate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new factory"""
    factory = factory_service.create_factory(
        db,
        factory_in=factory_in,
        workspace_id=workspace.id,
        user_id=current_user.id
    )
    return factory


@router.put(
    "/{factory_id}",
    response_model=FactoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Update factory",
    description="Update an existing factory"
)
def update_factory(
    factory_id: int,
    factory_in: FactoryUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update a factory"""
    factory = factory_service.update_factory(
        db,
        factory_id=factory_id,
        factory_in=factory_in,
        workspace_id=workspace.id,
        user_id=current_user.id
    )
    return factory


@router.delete(
    "/{factory_id}",
    response_model=FactoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete factory",
    description="Soft delete a factory"
)
def delete_factory(
    factory_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Soft delete a factory"""
    factory = factory_service.delete_factory(
        db,
        factory_id=factory_id,
        workspace_id=workspace.id,
        user_id=current_user.id
    )
    return factory
