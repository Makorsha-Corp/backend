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
    SalesOrderResponse,
    SalesOrderApproverCreate,
    SalesOrderApproverResponse,
    SalesOrderApprovalSummaryResponse,
    SalesOrderApproversList,
    SalesOrderSectionConfirmRequest,
    SalesOrderEventMetadata,
    SalesOrderEventResponse,
)
from app.schemas.sales_order_item import SalesOrderItemInput, SalesOrderItemListResponse
from app.schemas.response import ActionResponse
from app.services.sales_service import sales_service


router = APIRouter()


def _approver_response(record, profile=None, position=None) -> SalesOrderApproverResponse:
    return SalesOrderApproverResponse(
        id=record.id,
        workspace_id=record.workspace_id,
        sales_order_id=record.sales_order_id,
        user_id=record.user_id,
        user_name=profile.name if profile else None,
        user_email=profile.email if profile else None,
        user_position=position,
        assigned_by=record.assigned_by,
        assigned_at=record.assigned_at,
        approved=record.approved,
        approved_at=record.approved_at,
    )


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
        db, order_id, workspace.id, order_update, user_id=current_user.id
    )
    return order


@router.post(
    "/{order_id}/create-invoice",
    response_model=SalesOrderResponse,
    status_code=status.HTTP_200_OK,
    summary="Create invoice from sales order",
)
def create_invoice_from_sales_order(
    order_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return sales_service.create_invoice_for_sales_order(
        db,
        order_id=order_id,
        workspace_id=workspace.id,
        user_id=current_user.id,
    )


@router.post(
    "/{order_id}/finalize-invoice/",
    response_model=SalesOrderResponse,
    status_code=status.HTTP_200_OK,
    summary="Finalize the sales order's invoice",
    description=(
        "Creates the draft invoice if missing, confirms it, and locks the "
        "order's sections. Requires customer/details/items confirmed and approvals met."
    ),
)
def finalize_sales_order_invoice(
    order_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return sales_service.finalize_sales_order_invoice(
        db, order_id=order_id, workspace_id=workspace.id, user_id=current_user.id,
    )


@router.post(
    "/{order_id}/complete/",
    response_model=SalesOrderResponse,
    status_code=status.HTTP_200_OK,
    summary="Mark sales order complete",
    description="Allowed only when the invoice is finalized and every line has been delivered/fulfilled.",
)
def mark_sales_order_complete(
    order_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return sales_service.mark_order_complete(
        db, order_id=order_id, workspace_id=workspace.id, user_id=current_user.id,
    )


_SECTION_CONFIRM_FIELDS = {
    'customer': 'customer_confirmed',
    'details': 'details_confirmed',
    'items': 'items_confirmed',
}


@router.patch(
    "/{order_id}/section-confirm/",
    response_model=SalesOrderResponse,
    status_code=status.HTTP_200_OK,
    summary="Confirm or unconfirm a sales order section",
)
def set_sales_order_section_confirm(
    order_id: int,
    body: SalesOrderSectionConfirmRequest,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return sales_service.set_section_confirm(
        db, order_id=order_id, workspace_id=workspace.id, user_id=current_user.id,
        section=body.section, confirmed=body.confirmed,
    )


# ─── Sales Order Approvers ─────────────────────────────────────

@router.get(
    "/{order_id}/approvers/",
    response_model=SalesOrderApproversList,
    status_code=status.HTTP_200_OK,
    summary="List sales order approvers + approval summary",
)
def list_sales_order_approvers(
    order_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    rows = sales_service.list_approvers(db, order_id=order_id, workspace_id=workspace.id)
    order = sales_service.get_sales_order(db, order_id, workspace.id)
    approved_count, required, met = sales_service.approval_summary(db, order)
    return SalesOrderApproversList(
        approvers=[_approver_response(a, profile, position) for a, profile, position in rows],
        summary=SalesOrderApprovalSummaryResponse(approved_count=approved_count, required=required, met=met),
    )


@router.post(
    "/{order_id}/approvers/",
    response_model=SalesOrderApproverResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Assign an approver to a sales order",
)
def add_sales_order_approver(
    order_id: int,
    body: SalesOrderApproverCreate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    approver = sales_service.add_approver(
        db, order_id=order_id, user_id=body.user_id, workspace_id=workspace.id, assigned_by=current_user.id,
    )
    return _approver_response(approver)


@router.delete(
    "/{order_id}/approvers/{user_id}/",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove an approver from a sales order",
)
def remove_sales_order_approver(
    order_id: int,
    user_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    sales_service.remove_approver(
        db, order_id=order_id, user_id=user_id, workspace_id=workspace.id, performed_by=current_user.id,
    )


@router.post(
    "/{order_id}/approvers/me/approve/",
    response_model=SalesOrderApproverResponse,
    status_code=status.HTTP_200_OK,
    summary="Approve this sales order as the current user",
)
def approve_sales_order(
    order_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    approver = sales_service.set_approval(
        db, order_id=order_id, user_id=current_user.id, workspace_id=workspace.id, approved=True,
    )
    return _approver_response(approver)


@router.delete(
    "/{order_id}/approvers/me/approve/",
    response_model=SalesOrderApproverResponse,
    status_code=status.HTTP_200_OK,
    summary="Withdraw the current user's approval",
)
def unapprove_sales_order(
    order_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    approver = sales_service.set_approval(
        db, order_id=order_id, user_id=current_user.id, workspace_id=workspace.id, approved=False,
    )
    return _approver_response(approver)


# ─── Sales Order Events ────────────────────────────────────────

@router.get(
    "/{order_id}/events/",
    response_model=List[SalesOrderEventResponse],
    status_code=status.HTTP_200_OK,
    summary="List sales order activity events",
)
def list_sales_order_events(
    order_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    rows = sales_service.list_events(db, order_id=order_id, workspace_id=workspace.id)
    return [
        SalesOrderEventResponse(
            id=e.id,
            workspace_id=e.workspace_id,
            sales_order_id=e.sales_order_id,
            event_type=e.event_type,
            description=e.description,
            metadata=(
                SalesOrderEventMetadata.model_validate(e.metadata_json)
                if e.metadata_json
                else None
            ),
            performed_by=e.performed_by,
            user_name=profile.name if profile else None,
            created_at=e.created_at,
        )
        for e, profile in rows
    ]


@router.post(
    "/{order_id}/items/{item_id}/fulfill/",
    response_model=ActionResponse[SalesOrderResponse],
    status_code=status.HTTP_200_OK,
    summary="Fulfill a service or free-text sales order line",
    description=(
        "Marks a non-physical line item as fully delivered (quantity_delivered = quantity_ordered). "
        "No delivery record is created and no inventory/product stock is touched."
    ),
)
def fulfill_sales_order_item(
    order_id: int,
    item_id: int,
    db: Session = Depends(get_db),
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user)
):
    sales_order, messages = sales_service.fulfill_service_item(
        db, order_id=order_id, order_item_id=item_id, workspace_id=workspace.id, current_user=current_user
    )
    return ActionResponse(data=sales_order, messages=messages)


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
