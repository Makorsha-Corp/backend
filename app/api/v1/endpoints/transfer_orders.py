"""Transfer order API endpoints"""
from typing import List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_workspace, get_current_active_user
from app.dao.profile import profile_dao
from app.dao.workspace_member import workspace_member_dao
from app.models.workspace import Workspace
from app.models.profile import Profile
from app.schemas.transfer_order import (
    TransferOrderCreate, TransferOrderUpdate, TransferOrderResponse,
    TransferOrderItemCreate, TransferOrderItemUpdate, TransferOrderItemResponse,
    TransferOrderSectionConfirmRequest,
    TransferOrderApproverCreate, TransferOrderApproverResponse,
    ApprovalSummaryResponse, TransferOrderApproversList,
    TransferOrderEventMetadata, TransferOrderEventResponse,
)
from app.services.transfer_order_service import transfer_order_service


def _approver_response(record, profile=None, position=None) -> TransferOrderApproverResponse:
    return TransferOrderApproverResponse(
        id=record.id,
        workspace_id=record.workspace_id,
        transfer_order_id=record.transfer_order_id,
        user_id=record.user_id,
        user_name=profile.name if profile else None,
        user_email=profile.email if profile else None,
        user_position=position,
        assigned_by=record.assigned_by,
        assigned_at=record.assigned_at,
        approved=record.approved,
        approved_at=record.approved_at,
    )


_SECTION_CONFIRM_FIELDS = {
    'route': 'route_confirmed',
    'items': 'items_confirmed',
}


router = APIRouter()


# ─── Transfer Orders ───────────────────────────────────────────

@router.get(
    "/",
    response_model=List[TransferOrderResponse],
    status_code=status.HTTP_200_OK,
    summary="List transfer orders"
)
def list_transfer_orders(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    return transfer_order_service.list_transfer_orders(
        db, workspace_id=workspace.id,
        skip=skip, limit=limit
    )


@router.get(
    "/{to_id}/",
    response_model=TransferOrderResponse,
    status_code=status.HTTP_200_OK,
    summary="Get transfer order by ID"
)
def get_transfer_order(
    to_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    return transfer_order_service.get_transfer_order(db, to_id=to_id, workspace_id=workspace.id)


@router.post(
    "/",
    response_model=TransferOrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create transfer order"
)
def create_transfer_order(
    to_in: TransferOrderCreate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return transfer_order_service.create_transfer_order(
        db, to_in=to_in,
        workspace_id=workspace.id, user_id=current_user.id
    )


@router.put(
    "/{to_id}/",
    response_model=TransferOrderResponse,
    status_code=status.HTTP_200_OK,
    summary="Update transfer order"
)
def update_transfer_order(
    to_id: int,
    to_in: TransferOrderUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return transfer_order_service.update_transfer_order(
        db, to_id=to_id, to_in=to_in,
        workspace_id=workspace.id, user_id=current_user.id
    )


@router.patch(
    "/{to_id}/section-confirm/",
    response_model=TransferOrderResponse,
    status_code=status.HTTP_200_OK,
    summary="Confirm or unconfirm a transfer order section",
)
def set_transfer_order_section_confirm(
    to_id: int,
    body: TransferOrderSectionConfirmRequest,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    confirm_field = _SECTION_CONFIRM_FIELDS[body.section]
    return transfer_order_service.update_transfer_order(
        db,
        to_id=to_id,
        to_in=TransferOrderUpdate(**{confirm_field: body.confirmed}),
        workspace_id=workspace.id,
        user_id=current_user.id,
    )


@router.post(
    "/{to_id}/complete/",
    response_model=TransferOrderResponse,
    status_code=status.HTTP_200_OK,
    summary="Mark transfer order complete",
)
def mark_transfer_order_complete(
    to_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return transfer_order_service.mark_order_complete(
        db,
        to_id=to_id,
        workspace_id=workspace.id,
        user_id=current_user.id,
    )


@router.delete(
    "/{to_id}/",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete transfer order"
)
def delete_transfer_order(
    to_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    transfer_order_service.delete_transfer_order(db, to_id=to_id, workspace_id=workspace.id)


# ─── Transfer Order Approvers ──────────────────────────────────

@router.get(
    "/{to_id}/approvers/",
    response_model=TransferOrderApproversList,
    status_code=status.HTTP_200_OK,
    summary="List transfer order approvers + approval summary"
)
def list_transfer_order_approvers(
    to_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    rows = transfer_order_service.list_approvers(db, to_id=to_id, workspace_id=workspace.id)
    approved_count, required, met = transfer_order_service.approval_summary_for(
        db, to_id=to_id, workspace_id=workspace.id
    )
    return TransferOrderApproversList(
        approvers=[_approver_response(a, profile, position) for a, profile, position in rows],
        summary=ApprovalSummaryResponse(approved_count=approved_count, required=required, met=met),
    )


@router.post(
    "/{to_id}/approvers/",
    response_model=TransferOrderApproverResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Assign an approver to a transfer order"
)
def add_transfer_order_approver(
    to_id: int,
    body: TransferOrderApproverCreate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    record = transfer_order_service.add_approver(
        db, to_id=to_id, user_id=body.user_id,
        workspace_id=workspace.id, assigned_by=current_user.id
    )
    profile = profile_dao.get(db, id=record.user_id)
    member = workspace_member_dao.get_by_workspace_and_user(
        db, workspace_id=workspace.id, user_id=record.user_id
    )
    return _approver_response(record, profile, member.position if member else None)


@router.delete(
    "/{to_id}/approvers/{user_id}/",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove an approver from a transfer order"
)
def remove_transfer_order_approver(
    to_id: int,
    user_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    transfer_order_service.remove_approver(
        db, to_id=to_id, user_id=user_id,
        workspace_id=workspace.id, performed_by=current_user.id
    )


@router.post(
    "/{to_id}/approvers/me/approve/",
    response_model=TransferOrderApproverResponse,
    status_code=status.HTTP_200_OK,
    summary="Approve transfer order as current user"
)
def approve_transfer_order(
    to_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    record = transfer_order_service.set_approval(
        db, to_id=to_id, user_id=current_user.id,
        workspace_id=workspace.id, approved=True
    )
    member = workspace_member_dao.get_by_workspace_and_user(
        db, workspace_id=workspace.id, user_id=current_user.id
    )
    return _approver_response(record, current_user, member.position if member else None)


@router.delete(
    "/{to_id}/approvers/me/approve/",
    response_model=TransferOrderApproverResponse,
    status_code=status.HTTP_200_OK,
    summary="Withdraw transfer order approval as current user"
)
def unapprove_transfer_order(
    to_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    record = transfer_order_service.set_approval(
        db, to_id=to_id, user_id=current_user.id,
        workspace_id=workspace.id, approved=False
    )
    member = workspace_member_dao.get_by_workspace_and_user(
        db, workspace_id=workspace.id, user_id=current_user.id
    )
    return _approver_response(record, current_user, member.position if member else None)


# ─── Transfer Order Events ─────────────────────────────────────

@router.get(
    "/{to_id}/events/",
    response_model=List[TransferOrderEventResponse],
    status_code=status.HTTP_200_OK,
    summary="List transfer order activity events"
)
def list_transfer_order_events(
    to_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    rows = transfer_order_service.list_events(db, to_id=to_id, workspace_id=workspace.id)
    return [
        TransferOrderEventResponse(
            id=e.id,
            workspace_id=e.workspace_id,
            transfer_order_id=e.transfer_order_id,
            event_type=e.event_type,
            description=e.description,
            metadata=(
                TransferOrderEventMetadata.model_validate(e.metadata_json)
                if e.metadata_json
                else None
            ),
            performed_by=e.performed_by,
            user_name=profile.name if profile else None,
            created_at=e.created_at,
        )
        for e, profile in rows
    ]


# ─── Transfer Order Items ──────────────────────────────────────

@router.get(
    "/{to_id}/items/",
    response_model=List[TransferOrderItemResponse],
    status_code=status.HTTP_200_OK,
    summary="Get transfer order items"
)
def get_transfer_order_items(
    to_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    return transfer_order_service.get_items(db, to_id=to_id, workspace_id=workspace.id)


@router.post(
    "/{to_id}/items/",
    response_model=TransferOrderItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add item to transfer order"
)
def add_transfer_order_item(
    to_id: int,
    item_in: TransferOrderItemCreate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return transfer_order_service.add_item(
        db, to_id=to_id, item_in=item_in,
        workspace_id=workspace.id, user_id=current_user.id
    )


@router.put(
    "/items/{item_id}/",
    response_model=TransferOrderItemResponse,
    status_code=status.HTTP_200_OK,
    summary="Update transfer order item"
)
def update_transfer_order_item(
    item_id: int,
    item_in: TransferOrderItemUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return transfer_order_service.update_item(
        db, item_id=item_id, item_in=item_in,
        workspace_id=workspace.id, user_id=current_user.id
    )


@router.delete(
    "/items/{item_id}/",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove item from transfer order"
)
def remove_transfer_order_item(
    item_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    transfer_order_service.remove_item(
        db, item_id=item_id, workspace_id=workspace.id, user_id=current_user.id
    )
