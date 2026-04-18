"""Purchase order API endpoints"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_workspace, get_current_active_user
from app.models.workspace import Workspace
from app.models.profile import Profile
from app.schemas.purchase_order import (
    PurchaseOrderCreate, PurchaseOrderUpdate, PurchaseOrderResponse,
    PurchaseOrderItemCreate, PurchaseOrderItemUpdate, PurchaseOrderItemResponse,
)
from app.services.purchase_order_service import purchase_order_service


router = APIRouter()


# ─── Purchase Orders ───────────────────────────────────────────

@router.get(
    "/",
    response_model=List[PurchaseOrderResponse],
    status_code=status.HTTP_200_OK,
    summary="List purchase orders"
)
def list_purchase_orders(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    account_id: Optional[int] = Query(None),
    invoice_id: Optional[int] = Query(None),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    return purchase_order_service.list_purchase_orders(
        db, workspace_id=workspace.id,
        account_id=account_id,
        invoice_id=invoice_id,
        skip=skip, limit=limit
    )


@router.get(
    "/{po_id}/",
    response_model=PurchaseOrderResponse,
    status_code=status.HTTP_200_OK,
    summary="Get purchase order by ID"
)
def get_purchase_order(
    po_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    return purchase_order_service.get_purchase_order(db, po_id=po_id, workspace_id=workspace.id)


@router.post(
    "/",
    response_model=PurchaseOrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create purchase order"
)
def create_purchase_order(
    po_in: PurchaseOrderCreate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return purchase_order_service.create_purchase_order(
        db, po_in=po_in,
        workspace_id=workspace.id, user_id=current_user.id
    )


@router.put(
    "/{po_id}/",
    response_model=PurchaseOrderResponse,
    status_code=status.HTTP_200_OK,
    summary="Update purchase order"
)
def update_purchase_order(
    po_id: int,
    po_in: PurchaseOrderUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return purchase_order_service.update_purchase_order(
        db, po_id=po_id, po_in=po_in,
        workspace_id=workspace.id, user_id=current_user.id
    )


@router.delete(
    "/{po_id}/",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete purchase order"
)
def delete_purchase_order(
    po_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    purchase_order_service.delete_purchase_order(db, po_id=po_id, workspace_id=workspace.id)


@router.post(
    "/{po_id}/create-invoice",
    response_model=PurchaseOrderResponse,
    status_code=status.HTTP_200_OK,
    summary="Create invoice from purchase order"
)
def create_invoice_from_purchase_order(
    po_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return purchase_order_service.create_invoice_for_purchase_order(
        db,
        po_id=po_id,
        workspace_id=workspace.id,
        user_id=current_user.id
    )


# ─── Purchase Order Items ──────────────────────────────────────

@router.get(
    "/{po_id}/items/",
    response_model=List[PurchaseOrderItemResponse],
    status_code=status.HTTP_200_OK,
    summary="Get purchase order items"
)
def get_purchase_order_items(
    po_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    return purchase_order_service.get_items(db, po_id=po_id, workspace_id=workspace.id)


@router.post(
    "/{po_id}/items/",
    response_model=PurchaseOrderItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add item to purchase order"
)
def add_purchase_order_item(
    po_id: int,
    item_in: PurchaseOrderItemCreate,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    return purchase_order_service.add_item(
        db, po_id=po_id, item_in=item_in, workspace_id=workspace.id
    )


@router.put(
    "/items/{item_id}/",
    response_model=PurchaseOrderItemResponse,
    status_code=status.HTTP_200_OK,
    summary="Update purchase order item"
)
def update_purchase_order_item(
    item_id: int,
    item_in: PurchaseOrderItemUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    return purchase_order_service.update_item(
        db, item_id=item_id, item_in=item_in, workspace_id=workspace.id
    )


@router.delete(
    "/items/{item_id}/",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove item from purchase order"
)
def remove_purchase_order_item(
    item_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    purchase_order_service.remove_item(db, item_id=item_id, workspace_id=workspace.id)
