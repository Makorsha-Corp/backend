"""
Item endpoints

Provides CRUD operations for items (universal item catalog).
Items can be tagged as raw materials, machine parts, consumables, tools, or finished goods.
"""
from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_active_user, get_current_workspace
from app.models.profile import Profile
from app.models.workspace import Workspace
from app.schemas.item import ItemCreate, ItemUpdate, ItemResponse, ItemWithTagsResponse
from app.schemas.item_similar import SimilarItemsResponse
from app.schemas.item_orders import ItemOrdersListResponse, ItemOrderType
from app.schemas.item_summary import ItemSummaryResponse
from app.schemas.item_tag import ItemTagResponse
from app.services.item_service import item_service
from app.services.item_orders_service import item_orders_service
from app.services.item_summary_service import item_summary_service


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
    "/similar/",
    response_model=SimilarItemsResponse,
    status_code=status.HTTP_200_OK,
    summary="Find similar item names",
    description=(
        "Return active catalog items whose normalized names match or closely resemble "
        "the proposed name (spacing variants, typos). Used before creating duplicates."
    ),
)
def get_similar_items(
    name: str = Query(..., min_length=1, description="Proposed item name"),
    limit: int = Query(5, ge=1, le=10, description="Maximum matches to return"),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    return item_service.get_similar_items(
        db,
        workspace_id=workspace.id,
        name=name,
        limit=limit,
    )


@router.get(
    "/{item_id}/summary/",
    response_model=ItemSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get item summary hub",
    description="Aggregated catalog profile, stock, orders, pricing, and recent activity for one item.",
)
def get_item_summary(
    item_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    return item_summary_service.get_summary(
        db, item_id=item_id, workspace_id=workspace.id
    )


@router.get(
    "/{item_id}/orders/",
    response_model=ItemOrdersListResponse,
    status_code=status.HTTP_200_OK,
    summary="List orders containing an item",
    description=(
        "Returns purchase, transfer, sales, and work orders that include the item, "
        "one row per order. Optional date range and order type filters."
    ),
)
def get_item_orders(
    item_id: int,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of records to return"),
    order_type: Optional[ItemOrderType] = Query(
        None, description="Filter by order type"
    ),
    from_date: Optional[date] = Query(None, description="Inclusive start date (requires to_date)"),
    to_date: Optional[date] = Query(None, description="Inclusive end date (requires from_date)"),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    return item_orders_service.get_orders_for_item(
        db,
        workspace_id=workspace.id,
        item_id=item_id,
        skip=skip,
        limit=limit,
        order_type=order_type,
        from_date=from_date,
        to_date=to_date,
    )


@router.get(
    "/{item_id}/",
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
    "/{item_id}/",
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
    "/{item_id}/",
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
