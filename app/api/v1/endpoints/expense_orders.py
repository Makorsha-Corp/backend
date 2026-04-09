"""Expense order API endpoints"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_workspace, get_current_active_user
from app.models.workspace import Workspace
from app.models.profile import Profile
from app.schemas.expense_order import (
    ExpenseOrderCreate, ExpenseOrderUpdate, ExpenseOrderResponse,
    ExpenseOrderItemCreate, ExpenseOrderItemUpdate, ExpenseOrderItemResponse,
)
from app.services.expense_order_service import expense_order_service


router = APIRouter()


# ─── Expense Orders ───────────────────────────────────────────

@router.get(
    "/",
    response_model=List[ExpenseOrderResponse],
    status_code=status.HTTP_200_OK,
    summary="List expense orders"
)
def list_expense_orders(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    expense_category: Optional[str] = Query(None),
    account_id: Optional[int] = Query(None),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    return expense_order_service.list_expense_orders(
        db, workspace_id=workspace.id,
        expense_category=expense_category, account_id=account_id,
        skip=skip, limit=limit
    )


@router.get(
    "/{eo_id}/",
    response_model=ExpenseOrderResponse,
    status_code=status.HTTP_200_OK,
    summary="Get expense order by ID"
)
def get_expense_order(
    eo_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    return expense_order_service.get_expense_order(db, eo_id=eo_id, workspace_id=workspace.id)


@router.post(
    "/",
    response_model=ExpenseOrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create expense order"
)
def create_expense_order(
    eo_in: ExpenseOrderCreate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return expense_order_service.create_expense_order(
        db, eo_in=eo_in,
        workspace_id=workspace.id, user_id=current_user.id
    )


@router.put(
    "/{eo_id}/",
    response_model=ExpenseOrderResponse,
    status_code=status.HTTP_200_OK,
    summary="Update expense order"
)
def update_expense_order(
    eo_id: int,
    eo_in: ExpenseOrderUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return expense_order_service.update_expense_order(
        db, eo_id=eo_id, eo_in=eo_in,
        workspace_id=workspace.id, user_id=current_user.id
    )


@router.delete(
    "/{eo_id}/",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete expense order"
)
def delete_expense_order(
    eo_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    expense_order_service.delete_expense_order(db, eo_id=eo_id, workspace_id=workspace.id)


@router.post(
    "/{eo_id}/create-invoice",
    response_model=ExpenseOrderResponse,
    status_code=status.HTTP_200_OK,
    summary="Create invoice from expense order"
)
def create_invoice_from_expense_order(
    eo_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return expense_order_service.create_invoice_for_expense_order(
        db,
        eo_id=eo_id,
        workspace_id=workspace.id,
        user_id=current_user.id
    )


# ─── Expense Order Items ──────────────────────────────────────

@router.get(
    "/{eo_id}/items/",
    response_model=List[ExpenseOrderItemResponse],
    status_code=status.HTTP_200_OK,
    summary="Get expense order items"
)
def get_expense_order_items(
    eo_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    return expense_order_service.get_items(db, eo_id=eo_id, workspace_id=workspace.id)


@router.post(
    "/{eo_id}/items/",
    response_model=ExpenseOrderItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add item to expense order"
)
def add_expense_order_item(
    eo_id: int,
    item_in: ExpenseOrderItemCreate,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    return expense_order_service.add_item(
        db, eo_id=eo_id, item_in=item_in, workspace_id=workspace.id
    )


@router.put(
    "/items/{item_id}/",
    response_model=ExpenseOrderItemResponse,
    status_code=status.HTTP_200_OK,
    summary="Update expense order item"
)
def update_expense_order_item(
    item_id: int,
    item_in: ExpenseOrderItemUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    return expense_order_service.update_item(
        db, item_id=item_id, item_in=item_in, workspace_id=workspace.id
    )


@router.delete(
    "/items/{item_id}/",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove item from expense order"
)
def remove_expense_order_item(
    item_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    expense_order_service.remove_item(db, item_id=item_id, workspace_id=workspace.id)
