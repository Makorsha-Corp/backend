"""Order template API endpoints - reusable expense order templates"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_workspace, get_current_active_user
from app.models.workspace import Workspace
from app.models.profile import Profile
from app.schemas.order_template import (
    OrderTemplateCreate, OrderTemplateUpdate, OrderTemplateResponse,
    OrderTemplateItemCreate, OrderTemplateItemUpdate, OrderTemplateItemResponse,
)
from app.services.order_template_service import order_template_service


router = APIRouter()


# ─── Order Templates ──────────────────────────────────────────

@router.get(
    "/",
    response_model=List[OrderTemplateResponse],
    status_code=status.HTTP_200_OK,
    summary="List order templates"
)
def list_order_templates(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    is_active: Optional[bool] = Query(None),
    expense_category: Optional[str] = Query(None),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    return order_template_service.list_templates(
        db, workspace_id=workspace.id,
        is_active=is_active, expense_category=expense_category,
        skip=skip, limit=limit
    )


@router.get(
    "/{tpl_id}/",
    response_model=OrderTemplateResponse,
    status_code=status.HTTP_200_OK,
    summary="Get order template by ID"
)
def get_order_template(
    tpl_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    return order_template_service.get_template(db, tpl_id=tpl_id, workspace_id=workspace.id)


@router.post(
    "/",
    response_model=OrderTemplateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create order template"
)
def create_order_template(
    tpl_in: OrderTemplateCreate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return order_template_service.create_template(
        db, tpl_in=tpl_in,
        workspace_id=workspace.id, user_id=current_user.id
    )


@router.put(
    "/{tpl_id}/",
    response_model=OrderTemplateResponse,
    status_code=status.HTTP_200_OK,
    summary="Update order template"
)
def update_order_template(
    tpl_id: int,
    tpl_in: OrderTemplateUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return order_template_service.update_template(
        db, tpl_id=tpl_id, tpl_in=tpl_in,
        workspace_id=workspace.id, user_id=current_user.id
    )


@router.delete(
    "/{tpl_id}/",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete order template"
)
def delete_order_template(
    tpl_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    order_template_service.delete_template(db, tpl_id=tpl_id, workspace_id=workspace.id)


# ─── Template Items ───────────────────────────────────────────

@router.get(
    "/{tpl_id}/items/",
    response_model=List[OrderTemplateItemResponse],
    status_code=status.HTTP_200_OK,
    summary="Get template items"
)
def get_template_items(
    tpl_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    return order_template_service.get_items(db, tpl_id=tpl_id, workspace_id=workspace.id)


@router.post(
    "/{tpl_id}/items/",
    response_model=OrderTemplateItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add item to template"
)
def add_template_item(
    tpl_id: int,
    item_in: OrderTemplateItemCreate,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    return order_template_service.add_item(
        db, tpl_id=tpl_id, item_in=item_in, workspace_id=workspace.id
    )


@router.put(
    "/items/{item_id}/",
    response_model=OrderTemplateItemResponse,
    status_code=status.HTTP_200_OK,
    summary="Update template item"
)
def update_template_item(
    item_id: int,
    item_in: OrderTemplateItemUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    return order_template_service.update_item(
        db, item_id=item_id, item_in=item_in, workspace_id=workspace.id
    )


@router.delete(
    "/items/{item_id}/",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove item from template"
)
def remove_template_item(
    item_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    order_template_service.remove_item(db, item_id=item_id, workspace_id=workspace.id)
