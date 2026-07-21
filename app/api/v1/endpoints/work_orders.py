"""
Work order API endpoints

Provides operations for managing work orders, their approvals, lifecycle, and items.
"""
from typing import List, Optional
from datetime import date
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_workspace, get_current_active_user
from app.dao.profile import profile_dao
from app.dao.workspace_member import workspace_member_dao
from app.models.workspace import Workspace
from app.models.profile import Profile
from app.models.enums import WorkOrderPriorityEnum, WorkOrderStatusEnum
from app.schemas.work_order import (
    WorkOrderCreate, WorkOrderUpdate, WorkOrderResponse, WorkOrderVoidRequest,
    WorkOrderCompleteRequest,
    WorkOrderApproverCreate, WorkOrderApproverResponse,
    ApprovalSummaryResponse, WorkOrderApproversList,
    WorkOrderEventMetadata, WorkOrderEventResponse,
    WorkOrderSheetEntryCreate, WorkOrderSheetBundle,
    WorkOrderSheetDailyCountsResponse,
)
from app.schemas.work_order_item import WorkOrderItemCreate, WorkOrderItemUpdate, WorkOrderItemResponse
from app.schemas.work_order_template import WorkOrderFromTemplateCreate
from app.services.work_order_service import work_order_service


def _approver_response(record, profile=None, position=None) -> WorkOrderApproverResponse:
    return WorkOrderApproverResponse(
        id=record.id,
        workspace_id=record.workspace_id,
        work_order_id=record.work_order_id,
        user_id=record.user_id,
        user_name=profile.name if profile else None,
        user_email=profile.email if profile else None,
        user_position=position,
        assigned_by=record.assigned_by,
        assigned_at=record.assigned_at,
        approver_slot=getattr(record, 'approver_slot', None),
        approved=record.approved,
        approved_at=record.approved_at,
    )


router = APIRouter()


# ─── Work Orders ────────────────────────────────────────────────

@router.get(
    "/",
    response_model=List[WorkOrderResponse],
    status_code=status.HTTP_200_OK,
    summary="List work orders"
)
def list_work_orders(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    work_order_type_id: Optional[int] = Query(None),
    wo_status: Optional[WorkOrderStatusEnum] = Query(None, alias="status"),
    priority: Optional[WorkOrderPriorityEnum] = Query(None),
    factory_id: Optional[int] = Query(None),
    machine_id: Optional[int] = Query(None),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    return work_order_service.list_work_orders(
        db, workspace_id=workspace.id,
        work_order_type_id=work_order_type_id, wo_status=wo_status, priority=priority,
        factory_id=factory_id, machine_id=machine_id,
        skip=skip, limit=limit
    )


@router.get(
    "/sheet/",
    response_model=List[WorkOrderSheetBundle],
    status_code=status.HTTP_200_OK,
    summary="List work orders with embedded items for sheet view",
)
def list_work_orders_sheet(
    factory_id: Optional[int] = Query(None),
    machine_id: Optional[int] = Query(None),
    start_date_from: Optional[date] = Query(None),
    start_date_to: Optional[date] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(1000, ge=1, le=1000),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    return work_order_service.list_sheet_bundles(
        db,
        workspace_id=workspace.id,
        factory_id=factory_id,
        machine_id=machine_id,
        start_date_from=start_date_from,
        start_date_to=start_date_to,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/sheet/daily-counts/",
    response_model=WorkOrderSheetDailyCountsResponse,
    status_code=status.HTTP_200_OK,
    summary="Daily work-order counts for sheet calendar dots",
)
def list_work_orders_sheet_daily_counts(
    factory_id: Optional[int] = Query(None),
    machine_id: Optional[int] = Query(None),
    start_date_from: Optional[date] = Query(None),
    start_date_to: Optional[date] = Query(None),
    wo_status: Optional[WorkOrderStatusEnum] = Query(None, alias="status"),
    work_order_type_id: Optional[int] = Query(None),
    priority: Optional[WorkOrderPriorityEnum] = Query(None),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    return work_order_service.sheet_daily_counts(
        db,
        workspace_id=workspace.id,
        factory_id=factory_id,
        machine_id=machine_id,
        start_date_from=start_date_from,
        start_date_to=start_date_to,
        status=wo_status,
        work_order_type_id=work_order_type_id,
        priority=priority,
    )


@router.post(
    "/sheet-entry/",
    response_model=WorkOrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Sheet row entry — find-or-create WO and append consumable lines",
)
def create_work_order_sheet_entry(
    body: WorkOrderSheetEntryCreate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return work_order_service.sheet_entry(
        db, data=body, workspace_id=workspace.id, user_id=current_user.id
    )


@router.get(
    "/{wo_id}/",
    response_model=WorkOrderResponse,
    status_code=status.HTTP_200_OK,
    summary="Get work order by ID"
)
def get_work_order(
    wo_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    return work_order_service.get_work_order(db, wo_id=wo_id, workspace_id=workspace.id)


@router.post(
    "/",
    response_model=WorkOrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create work order"
)
def create_work_order(
    wo_in: WorkOrderCreate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return work_order_service.create_work_order(
        db, wo_in=wo_in,
        workspace_id=workspace.id, user_id=current_user.id
    )


@router.post(
    "/from-template/{template_id}/",
    response_model=WorkOrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create work order from a saved template"
)
def create_work_order_from_template(
    template_id: int,
    overrides: WorkOrderFromTemplateCreate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return work_order_service.create_work_order_from_template(
        db, template_id=template_id, overrides=overrides,
        workspace_id=workspace.id, user_id=current_user.id
    )


@router.put(
    "/{wo_id}/",
    response_model=WorkOrderResponse,
    status_code=status.HTTP_200_OK,
    summary="Update work order"
)
def update_work_order(
    wo_id: int,
    wo_in: WorkOrderUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return work_order_service.update_work_order(
        db, wo_id=wo_id, wo_in=wo_in,
        workspace_id=workspace.id, user_id=current_user.id
    )


@router.post(
    "/{wo_id}/start/",
    response_model=WorkOrderResponse,
    status_code=status.HTTP_200_OK,
    summary="Start work — consumes any inventory items and moves to In Progress",
)
def start_work_order(
    wo_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return work_order_service.start_work_order(db, wo_id=wo_id, workspace_id=workspace.id, user_id=current_user.id)


@router.post(
    "/{wo_id}/complete/",
    response_model=WorkOrderResponse,
    status_code=status.HTTP_200_OK,
    summary="Mark work order complete",
)
def complete_work_order(
    wo_id: int,
    body: WorkOrderCompleteRequest = WorkOrderCompleteRequest(),
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return work_order_service.complete_work_order(
        db, wo_id=wo_id, workspace_id=workspace.id, user_id=current_user.id,
        completion_notes=body.completion_notes, machine_status=body.machine_status,
    )


@router.post(
    "/{wo_id}/void/",
    response_model=WorkOrderResponse,
    status_code=status.HTTP_200_OK,
    summary="Void work order",
    description="Voids the work order, reversing any inventory already consumed. Only allowed before completion.",
)
def void_work_order(
    wo_id: int,
    body: WorkOrderVoidRequest,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return work_order_service.void_work_order(
        db, wo_id=wo_id, workspace_id=workspace.id, user_id=current_user.id, void_note=body.void_note,
    )


@router.delete(
    "/{wo_id}/",
    response_model=WorkOrderResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete work order"
)
def delete_work_order(
    wo_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return work_order_service.delete_work_order(
        db, wo_id=wo_id,
        workspace_id=workspace.id, user_id=current_user.id
    )


@router.post(
    "/{wo_id}/create-invoice",
    response_model=WorkOrderResponse,
    status_code=status.HTTP_200_OK,
    summary="Create invoice from work order (requires an account set)"
)
def create_invoice_from_work_order(
    wo_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return work_order_service.create_invoice_for_work_order(
        db, wo_id=wo_id, workspace_id=workspace.id, user_id=current_user.id
    )


# ─── Work Order Approvers ──────────────────────────────────────

@router.get(
    "/{wo_id}/approvers/",
    response_model=WorkOrderApproversList,
    status_code=status.HTTP_200_OK,
    summary="List work order approvers + approval summary"
)
def list_work_order_approvers(
    wo_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    rows = work_order_service.list_approvers(db, wo_id=wo_id, workspace_id=workspace.id)
    approved_count, required, met = work_order_service.approval_summary_for(db, wo_id=wo_id, workspace_id=workspace.id)
    return WorkOrderApproversList(
        approvers=[_approver_response(a, profile, position) for a, profile, position in rows],
        summary=ApprovalSummaryResponse(approved_count=approved_count, required=required, met=met),
    )


@router.post(
    "/{wo_id}/approvers/",
    response_model=WorkOrderApproverResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Assign an approver to a work order"
)
def add_work_order_approver(
    wo_id: int,
    body: WorkOrderApproverCreate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    record = work_order_service.add_approver(
        db, wo_id=wo_id, user_id=body.user_id, workspace_id=workspace.id,
        assigned_by=current_user.id, approver_slot=body.approver_slot,
    )
    profile = profile_dao.get(db, id=record.user_id)
    member = workspace_member_dao.get_by_workspace_and_user(db, workspace_id=workspace.id, user_id=record.user_id)
    return _approver_response(record, profile, member.position if member else None)


@router.delete(
    "/{wo_id}/approvers/{user_id}/",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove an approver from a work order"
)
def remove_work_order_approver(
    wo_id: int,
    user_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    work_order_service.remove_approver(db, wo_id=wo_id, user_id=user_id, workspace_id=workspace.id, performed_by=current_user.id)


@router.post(
    "/{wo_id}/approvers/me/approve/",
    response_model=WorkOrderApproverResponse,
    status_code=status.HTTP_200_OK,
    summary="Approve work order as current user"
)
def approve_work_order(
    wo_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    record = work_order_service.approve_as_me(db, wo_id=wo_id, user_id=current_user.id, workspace_id=workspace.id)
    member = workspace_member_dao.get_by_workspace_and_user(db, workspace_id=workspace.id, user_id=current_user.id)
    return _approver_response(record, current_user, member.position if member else None)


@router.delete(
    "/{wo_id}/approvers/me/approve/",
    response_model=WorkOrderApproverResponse,
    status_code=status.HTTP_200_OK,
    summary="Withdraw work order approval as current user"
)
def unapprove_work_order(
    wo_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    record = work_order_service.unapprove_as_me(db, wo_id=wo_id, user_id=current_user.id, workspace_id=workspace.id)
    member = workspace_member_dao.get_by_workspace_and_user(db, workspace_id=workspace.id, user_id=current_user.id)
    return _approver_response(record, current_user, member.position if member else None)


# ─── Work Order Events ──────────────────────────────────────────

@router.get(
    "/{wo_id}/events/",
    response_model=List[WorkOrderEventResponse],
    status_code=status.HTTP_200_OK,
    summary="List work order activity events"
)
def list_work_order_events(
    wo_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    rows = work_order_service.list_events(db, wo_id=wo_id, workspace_id=workspace.id)
    return [
        WorkOrderEventResponse(
            id=e.id,
            workspace_id=e.workspace_id,
            work_order_id=e.work_order_id,
            event_type=e.event_type,
            description=e.description,
            metadata=(WorkOrderEventMetadata.model_validate(e.metadata_json) if e.metadata_json else None),
            performed_by=e.performed_by,
            user_name=profile.name if profile else None,
            created_at=e.created_at,
        )
        for e, profile in rows
    ]


# ─── Work Order Items ───────────────────────────────────────────

@router.get(
    "/{wo_id}/items/",
    response_model=List[WorkOrderItemResponse],
    status_code=status.HTTP_200_OK,
    summary="Get work order items"
)
def get_work_order_items(
    wo_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    return work_order_service.get_items(db, wo_id=wo_id, workspace_id=workspace.id)


@router.post(
    "/{wo_id}/items/",
    response_model=WorkOrderItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add item to work order"
)
def add_work_order_item(
    wo_id: int,
    item_in: WorkOrderItemCreate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    item_in.work_order_id = wo_id
    return work_order_service.add_item(
        db, item_in=item_in,
        workspace_id=workspace.id, user_id=current_user.id
    )


@router.put(
    "/{wo_id}/items/{item_id}/",
    response_model=WorkOrderItemResponse,
    status_code=status.HTTP_200_OK,
    summary="Update work order item"
)
def update_work_order_item(
    wo_id: int,
    item_id: int,
    item_in: WorkOrderItemUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return work_order_service.update_item(
        db, item_id=item_id, item_in=item_in,
        workspace_id=workspace.id, user_id=current_user.id
    )


@router.delete(
    "/{wo_id}/items/{item_id}/",
    response_model=WorkOrderItemResponse,
    status_code=status.HTTP_200_OK,
    summary="Remove item from work order"
)
def remove_work_order_item(
    wo_id: int,
    item_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return work_order_service.remove_item(
        db, item_id=item_id, workspace_id=workspace.id, user_id=current_user.id
    )
