"""Work order template API endpoints - reusable "things that happen all the time" presets"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_workspace, get_current_active_user
from app.models.workspace import Workspace
from app.models.profile import Profile
from app.dao.profile import profile_dao
from app.schemas.work_order_template import (
    WorkOrderTemplateCreate, WorkOrderTemplateUpdate, WorkOrderTemplateResponse,
    WorkOrderTemplateItemCreate, WorkOrderTemplateItemUpdate, WorkOrderTemplateItemResponse,
    WorkOrderTemplateApproverResponse, GenerateWorkOrderDraftsRequest,
)
from app.schemas.work_order import WorkOrderResponse
from app.services.work_order_template_service import work_order_template_service


router = APIRouter()


# ─── Work Order Templates ────────────────────────────────────

@router.get(
    "/",
    response_model=List[WorkOrderTemplateResponse],
    status_code=status.HTTP_200_OK,
    summary="List work order templates"
)
def list_work_order_templates(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    is_active: Optional[bool] = Query(True),
    work_order_type_id: Optional[int] = Query(None),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    return work_order_template_service.list_templates(
        db, workspace_id=workspace.id,
        is_active=is_active, work_order_type_id=work_order_type_id,
        skip=skip, limit=limit
    )


@router.post(
    "/generate-drafts/",
    response_model=List[WorkOrderResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Generate draft work orders from recurring/section templates",
)
def generate_work_order_drafts(
    body: GenerateWorkOrderDraftsRequest,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return work_order_template_service.generate_drafts(
        db, body=body, workspace_id=workspace.id, user_id=current_user.id,
    )


@router.get(
    "/{tpl_id}/",
    response_model=WorkOrderTemplateResponse,
    status_code=status.HTTP_200_OK,
    summary="Get work order template by ID"
)
def get_work_order_template(
    tpl_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    return work_order_template_service.get_template(db, tpl_id=tpl_id, workspace_id=workspace.id)


@router.post(
    "/",
    response_model=WorkOrderTemplateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create work order template"
)
def create_work_order_template(
    tpl_in: WorkOrderTemplateCreate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return work_order_template_service.create_template(
        db, tpl_in=tpl_in, workspace_id=workspace.id, user_id=current_user.id
    )


@router.put(
    "/{tpl_id}/",
    response_model=WorkOrderTemplateResponse,
    status_code=status.HTTP_200_OK,
    summary="Update work order template"
)
def update_work_order_template(
    tpl_id: int,
    tpl_in: WorkOrderTemplateUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return work_order_template_service.update_template(
        db, tpl_id=tpl_id, tpl_in=tpl_in, workspace_id=workspace.id, user_id=current_user.id
    )


@router.delete(
    "/{tpl_id}/",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deactivate work order template"
)
def delete_work_order_template(
    tpl_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    work_order_template_service.delete_template(db, tpl_id=tpl_id, workspace_id=workspace.id, user_id=current_user.id)


@router.post(
    "/{tpl_id}/restore/",
    response_model=WorkOrderTemplateResponse,
    status_code=status.HTTP_200_OK,
    summary="Reactivate work order template"
)
def restore_work_order_template(
    tpl_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return work_order_template_service.restore_template(db, tpl_id=tpl_id, workspace_id=workspace.id, user_id=current_user.id)


# ─── Template Items ───────────────────────────────────────────

@router.get(
    "/{tpl_id}/items/",
    response_model=List[WorkOrderTemplateItemResponse],
    status_code=status.HTTP_200_OK,
    summary="Get template items"
)
def get_template_items(
    tpl_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    return work_order_template_service.get_items(db, tpl_id=tpl_id, workspace_id=workspace.id)


@router.post(
    "/{tpl_id}/items/",
    response_model=WorkOrderTemplateItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add item to template"
)
def add_template_item(
    tpl_id: int,
    item_in: WorkOrderTemplateItemCreate,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    return work_order_template_service.add_item(db, tpl_id=tpl_id, item_in=item_in, workspace_id=workspace.id)


@router.put(
    "/items/{item_id}/",
    response_model=WorkOrderTemplateItemResponse,
    status_code=status.HTTP_200_OK,
    summary="Update template item"
)
def update_template_item(
    item_id: int,
    item_in: WorkOrderTemplateItemUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    return work_order_template_service.update_item(db, item_id=item_id, item_in=item_in, workspace_id=workspace.id)


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
    work_order_template_service.remove_item(db, item_id=item_id, workspace_id=workspace.id)


# ─── Template Approvers ───────────────────────────────────────

@router.get(
    "/{tpl_id}/approvers/",
    response_model=List[WorkOrderTemplateApproverResponse],
    status_code=status.HTTP_200_OK,
    summary="Get template default approvers"
)
def get_template_approvers(
    tpl_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    rows = work_order_template_service.get_approvers(db, tpl_id=tpl_id, workspace_id=workspace.id)
    result = []
    for r in rows:
        profile = profile_dao.get(db, id=r.user_id)
        result.append(WorkOrderTemplateApproverResponse(
            id=r.id, workspace_id=r.workspace_id, work_order_template_id=r.work_order_template_id,
            user_id=r.user_id, user_name=profile.name if profile else None,
        ))
    return result
