"""
Delivery Method API endpoints

Provides operations for managing delivery methods (Courier, Pickup, Own Fleet, etc.)
used to tag how a sales delivery is shipped.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_active_user, get_current_workspace
from app.models.profile import Profile
from app.models.workspace import Workspace
from app.schemas.delivery_method import DeliveryMethodCreate, DeliveryMethodUpdate, DeliveryMethodResponse
from app.services.delivery_method_service import delivery_method_service


router = APIRouter()


@router.get(
    "/",
    response_model=List[DeliveryMethodResponse],
    status_code=status.HTTP_200_OK,
    summary="List all delivery methods",
    description="Get all delivery methods in the workspace with optional search"
)
def get_delivery_methods(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    search: Optional[str] = Query(None, description="Search by name"),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Get all delivery methods in workspace"""
    delivery_methods = delivery_method_service.get_delivery_methods(
        db,
        workspace_id=workspace.id,
        search=search,
        skip=skip,
        limit=limit
    )
    return delivery_methods


@router.get(
    "/{delivery_method_id}/",
    response_model=DeliveryMethodResponse,
    status_code=status.HTTP_200_OK,
    summary="Get delivery method by ID",
    description="Get a specific delivery method by ID"
)
def get_delivery_method(
    delivery_method_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Get a specific delivery method"""
    delivery_method = delivery_method_service.get_delivery_method(
        db,
        delivery_method_id=delivery_method_id,
        workspace_id=workspace.id
    )
    return delivery_method


@router.post(
    "/",
    response_model=DeliveryMethodResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new delivery method",
    description="Create a new delivery method"
)
def create_delivery_method(
    delivery_method_in: DeliveryMethodCreate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new delivery method"""
    delivery_method = delivery_method_service.create_delivery_method(
        db,
        delivery_method_in=delivery_method_in,
        workspace_id=workspace.id,
        user_id=current_user.id
    )
    return delivery_method


@router.put(
    "/{delivery_method_id}/",
    response_model=DeliveryMethodResponse,
    status_code=status.HTTP_200_OK,
    summary="Update delivery method",
    description="Update an existing delivery method"
)
def update_delivery_method(
    delivery_method_id: int,
    delivery_method_in: DeliveryMethodUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update a delivery method"""
    delivery_method = delivery_method_service.update_delivery_method(
        db,
        delivery_method_id=delivery_method_id,
        delivery_method_in=delivery_method_in,
        workspace_id=workspace.id,
        user_id=current_user.id
    )
    return delivery_method


@router.delete(
    "/{delivery_method_id}/",
    response_model=DeliveryMethodResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete delivery method",
    description="Soft delete a delivery method"
)
def delete_delivery_method(
    delivery_method_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Soft delete a delivery method"""
    delivery_method = delivery_method_service.delete_delivery_method(
        db,
        delivery_method_id=delivery_method_id,
        workspace_id=workspace.id,
        user_id=current_user.id
    )
    return delivery_method
