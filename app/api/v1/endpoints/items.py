"""
Item endpoints

Provides CRUD operations for items (universal item catalog).
Items can be tagged as raw materials, machine parts, consumables, tools, or finished goods.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_active_user, get_current_workspace
from app.models.profile import Profile
from app.models.workspace import Workspace
from app.schemas.item import ItemCreate, ItemUpdate, ItemResponse, ItemWithTagsResponse
from app.schemas.item_tag import ItemTagResponse
from app.services.item_service import item_service


router = APIRouter()


@router.get(
    "/",
    response_model=List[ItemWithTagsResponse],
    status_code=status.HTTP_200_OK,
    summary="List all items with tags",
    description="""
    Get all items with their tags included, with pagination and optional search.

    Returns direct list of items with tags (no wrapper).
    """
)
def get_items(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, le=100, description="Maximum number of records to return"),
    search: Optional[str] = Query(None, description="Search by item name"),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Get all items with their tags included"""
    items = item_service.get_items_with_tags(db, workspace_id=workspace.id, search=search, skip=skip, limit=limit)
    return items


@router.get(
    "/{item_id}",
    response_model=ItemResponse,
    status_code=status.HTTP_200_OK,
    summary="Get item by ID",
    description="Retrieve a single item by its ID. Raises 404 if not found."
)
def get_item(
    item_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """
    Get item by ID.

    Service layer will raise NotFoundError if item doesn't exist,
    which will be caught by exception handler and returned as RFC 7807 error.
    """
    item = item_service.get_item(db, item_id, workspace_id=workspace.id)
    return item


@router.post(
    "/",
    response_model=ItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new item",
    description="Create a new item in the catalog. Returns the created item."
)
def create_item(
    item_in: ItemCreate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Create new item.

    Returns created item directly (no wrapper).
    Any exceptions are handled by global exception handlers.
    """
    item = item_service.create_item(db, item_in, workspace.id, current_user.id)
    return item


@router.put(
    "/{item_id}",
    response_model=ItemResponse,
    status_code=status.HTTP_200_OK,
    summary="Update item",
    description="Update an existing item. Returns the updated item."
)
def update_item(
    item_id: int,
    item_in: ItemUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Update item.

    Service layer will raise NotFoundError if item doesn't exist.
    Returns updated item directly (no wrapper).
    """
    item = item_service.update_item(db, item_id, item_in, workspace.id, current_user.id)
    return item


@router.delete(
    "/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete item",
    description="Soft delete an item (sets is_active=False). Returns 204 No Content on success."
)
def delete_item(
    item_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Delete item (soft delete).

    Service layer will raise NotFoundError if item doesn't exist.
    Returns 204 No Content on success (no body).
    """
    item_service.delete_item(db, item_id, workspace.id, current_user.id)
