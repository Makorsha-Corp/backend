"""
Sales delivery endpoints

Provides CRUD operations for sales deliveries and complex delivery completion workflow.
Each delivery is a partial fulfillment of a sales order contract.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Body, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_active_user, get_current_workspace
from app.models.profile import Profile
from app.models.workspace import Workspace
from app.schemas.sales_delivery import (
    SalesDeliveryCreate,
    SalesDeliveryUpdate,
    SalesDeliveryResponse
)
from app.schemas.sales_delivery_item import SalesDeliveryItemCreate, SalesDeliveryItemInput
from app.schemas.sales_order import SalesOrderResponse
from app.schemas.response import ActionResponse
from app.services.sales_service import sales_service


router = APIRouter()


@router.get(
    "/",
    response_model=List[SalesDeliveryResponse],
    status_code=status.HTTP_200_OK,
    summary="List deliveries",
    description="Get all deliveries for workspace with pagination and optional status filter."
)
def get_deliveries(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, le=100, description="Maximum number of records to return"),
    delivery_status: Optional[str] = Query(None, description="Filter by delivery status (planned, delivered, cancelled)"),
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user)
):
    """Get all deliveries for workspace with optional status filter"""
    deliveries = sales_service.get_deliveries(
        db, workspace_id=workspace.id, delivery_status=delivery_status, skip=skip, limit=limit
    )
    return deliveries


@router.get(
    "/{delivery_id}",
    response_model=SalesDeliveryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get delivery by ID",
    description="Retrieve a single delivery. Raises 404 if not found."
)
def get_delivery(
    delivery_id: int,
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user)
):
    """
    Get delivery by ID.

    Service layer will raise NotFoundError if delivery doesn't exist.
    """
    delivery = sales_service.get_delivery(db, delivery_id, workspace.id)
    return delivery


@router.post(
    "/",
    response_model=SalesDeliveryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create delivery",
    description="Create new delivery for a sales order with line items. Returns created delivery."
)
def create_delivery(
    delivery_in: SalesDeliveryCreate,
    items: List[SalesDeliveryItemInput] = Body(..., description="List of items in this delivery"),
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user)
):
    """
    Create new delivery for a sales order.

    Returns created delivery directly (no wrapper).
    Service handles validation and raises appropriate exceptions.

    Note: items should only reference sales_order_item_id from the parent order.
    The item_id will be automatically derived from the sales order item.
    """
    # Convert items to dict for service layer
    items_data = [item.model_dump() for item in items]

    delivery, sales_order = sales_service.create_delivery(
        db, delivery_in, items_data, workspace.id, current_user
    )
    return delivery


@router.post(
    "/{delivery_id}/complete",
    response_model=ActionResponse[SalesOrderResponse],
    status_code=200
)
def complete_delivery(
    delivery_id: int,
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user)
):
    """
    Complete delivery and perform all related backend actions.

    **Backend Actions Performed:**
    1. Mark delivery as completed
    2. Update sales order item quantities delivered
    3. Update inventory ledger (transfer_out)
    4. Update inventory snapshot (deduct stock)
    5. Check if sales order fully delivered
    6. Auto-generate invoice if configured (future)

    **Response includes:**
    - Updated sales order data
    - List of messages describing each action performed

    Args:
        delivery_id: Delivery ID
        db: Database session
        workspace: Current workspace
        current_user: Current authenticated user

    Returns:
        ActionResponse with sales order and action messages

    Raises:
        404: Delivery not found
        422: Business rule violation
        500: Internal server error
    """
    # Service handles all logic and returns messages
    sales_order, messages = sales_service.complete_delivery(
        db, delivery_id, workspace.id, current_user
    )

    return ActionResponse(
        data=sales_order,
        messages=messages
    )


@router.get(
    "/{delivery_id}/items",
    status_code=status.HTTP_200_OK,
    summary="Get delivery items",
    description="Get all line items for a delivery."
)
def get_delivery_items(
    delivery_id: int,
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user)
):
    """Get all items for a delivery"""
    items = sales_service.get_delivery_items(
        db, delivery_id=delivery_id, workspace_id=workspace.id
    )
    return items
