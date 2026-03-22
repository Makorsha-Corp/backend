"""
Sales order endpoints

Provides CRUD operations for sales orders (customer contracts with deliveries).
Sales orders link to customer accounts and can have multiple deliveries over time.
"""
from typing import List, Optional  # List used for response_model
from fastapi import APIRouter, Depends, Query, Body, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_active_user, get_current_workspace
from app.models.profile import Profile
from app.models.workspace import Workspace
from app.schemas.sales_order import (
    SalesOrderCreate,
    SalesOrderUpdate,
    SalesOrderResponse
)
from app.schemas.sales_order_item import SalesOrderItemInput, SalesOrderItemListResponse
from app.services.sales_service import sales_service


router = APIRouter()


@router.get(
    "/",
    response_model=List[SalesOrderResponse],
    status_code=status.HTTP_200_OK,
    summary="List sales orders",
    description="Get all sales orders for workspace with pagination. Returns direct list (no wrapper)."
)
def get_sales_orders(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, le=100, description="Maximum number of records to return"),
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user)
):
    """Get all sales orders for workspace with pagination"""
    orders = sales_service.get_sales_orders(
        db, workspace_id=workspace.id, skip=skip, limit=limit
    )
    return orders


@router.get(
    "/{order_id}/",
    response_model=SalesOrderResponse,
    status_code=status.HTTP_200_OK,
    summary="Get sales order by ID",
    description="Retrieve a single sales order. Raises 404 if not found."
)
def get_sales_order(
    order_id: int,
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user)
):
    """
    Get sales order by ID.

    Service layer will raise NotFoundError if order doesn't exist.
    """
    order = sales_service.get_sales_order(db, order_id, workspace.id)
    return order


@router.post(
    "/",
    response_model=SalesOrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create sales order",
    description="Create new sales order with line items. Total amount calculated from items."
)
def create_sales_order(
    order_in: SalesOrderCreate,
    items: List[SalesOrderItemInput] = Body(..., description="List of items to sell"),
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user)
):
    """
    Create new sales order with items.

    Returns created order directly (no wrapper).
    Service handles validation and raises appropriate exceptions.

    Note: total_amount and line_total are calculated automatically from items.
    """
    from decimal import Decimal

    # Convert items to dict and calculate line_total for each
    items_data = []
    total_amount = Decimal('0')

    for item in items:
        item_dict = item.model_dump()
        line_total = Decimal(str(item.quantity_ordered)) * item.unit_price
        item_dict['line_total'] = line_total
        total_amount += line_total
        items_data.append(item_dict)

    # Add total_amount to order data
    order_data = order_in.model_dump(exclude_none=False)
    order_data['total_amount'] = total_amount

    # Ensure current_status_id has a default (10 = "Started" status for workspace 1)
    if 'current_status_id' not in order_data or order_data['current_status_id'] is None:
        order_data['current_status_id'] = 10

    # Service will handle converting dict to schema
    order = sales_service.create_sales_order_from_dict(
        db, order_data, items_data, workspace.id, current_user
    )
    return order


@router.put(
    "/{order_id}/",
    response_model=SalesOrderResponse,
    status_code=status.HTTP_200_OK,
    summary="Update sales order",
    description="Update an existing sales order. Returns updated order."
)
def update_sales_order(
    order_id: int,
    order_update: SalesOrderUpdate,
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user)
):
    """
    Update sales order.

    Service layer will raise NotFoundError if order doesn't exist.
    """
    order = sales_service.update_sales_order(
        db, order_id, workspace.id, order_update
    )
    return order


@router.get(
    "/{order_id}/items/",
    response_model=List[SalesOrderItemListResponse],
    status_code=status.HTTP_200_OK,
    summary="Get sales order items",
    description="Get all line items for a sales order."
)
def get_sales_order_items(
    order_id: int,
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user)
):
    """Get all items for a sales order"""
    items = sales_service.get_sales_order_items(
        db, sales_order_id=order_id, workspace_id=workspace.id
    )
    return items


@router.get(
    "/{order_id}/deliveries/",
    status_code=status.HTTP_200_OK,
    summary="Get sales order deliveries",
    description="Get all deliveries for a sales order."
)
def get_sales_order_deliveries(
    order_id: int,
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user)
):
    """Get all deliveries for a sales order"""
    deliveries = sales_service.get_deliveries_for_order(
        db, order_id, workspace.id
    )
    return deliveries
