"""Purchase order API endpoints"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_workspace, get_current_active_user
from app.models.workspace import Workspace
from app.models.profile import Profile
from app.dao.profile import profile_dao
from app.dao.workspace_member import workspace_member_dao
from app.schemas.purchase_order import (
    PurchaseOrderCreate, PurchaseOrderUpdate, PurchaseOrderResponse,
    PurchaseOrderItemCreate, PurchaseOrderItemUpdate, PurchaseOrderItemResponse,
    PurchaseOrderItemSyncRequest,
    ActiveOrderRow,
    PurchaseOrderApproverCreate, PurchaseOrderApproverResponse,
    ApprovalSummaryResponse, PurchaseOrderApproversList,
    PurchaseOrderEventMetadata,
    PurchaseOrderEventResponse,
    PurchaseOrderSectionConfirmRequest,
)
from app.services.purchase_order_service import purchase_order_service


def _approver_response(record, profile=None, position=None) -> PurchaseOrderApproverResponse:
    return PurchaseOrderApproverResponse(
        id=record.id,
        workspace_id=record.workspace_id,
        purchase_order_id=record.purchase_order_id,
        user_id=record.user_id,
        user_name=profile.name if profile else None,
        user_email=profile.email if profile else None,
        user_position=position,
        assigned_by=record.assigned_by,
        assigned_at=record.assigned_at,
        approved=record.approved,
        approved_at=record.approved_at,
    )


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
    "/active/",
    response_model=List[ActiveOrderRow],
    status_code=status.HTTP_200_OK,
    summary="Active orders for a machine, factory storage, or project component",
    description="Exactly one of machine_id, factory_id, or project_component_id must be set.",
)
def list_active_orders_for_context(
    machine_id: Optional[int] = Query(None),
    factory_id: Optional[int] = Query(None),
    project_component_id: Optional[int] = Query(None),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db),
):
    return purchase_order_service.list_active_orders_for_context(
        db,
        workspace_id=workspace.id,
        machine_id=machine_id,
        factory_id=factory_id,
        project_component_id=project_component_id,
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


_SECTION_CONFIRM_FIELDS = {
    'supplier': 'supplier_confirmed',
    'details': 'details_confirmed',
    'notes': 'notes_confirmed',
    'items': 'items_confirmed',
    'invoice': 'invoice_confirmed',
}


@router.patch(
    "/{po_id}/section-confirm/",
    response_model=PurchaseOrderResponse,
    status_code=status.HTTP_200_OK,
    summary="Confirm or unconfirm a purchase order section",
)
def set_purchase_order_section_confirm(
    po_id: int,
    body: PurchaseOrderSectionConfirmRequest,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    confirm_field = _SECTION_CONFIRM_FIELDS[body.section]
    return purchase_order_service.update_purchase_order(
        db,
        po_id=po_id,
        po_in=PurchaseOrderUpdate(**{confirm_field: body.confirmed}),
        workspace_id=workspace.id,
        user_id=current_user.id,
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


# ─── Purchase Order Approvers ──────────────────────────────────

@router.get(
    "/{po_id}/approvers/",
    response_model=PurchaseOrderApproversList,
    status_code=status.HTTP_200_OK,
    summary="List purchase order approvers + approval summary"
)
def list_purchase_order_approvers(
    po_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    rows = purchase_order_service.list_approvers(db, po_id=po_id, workspace_id=workspace.id)
    approved_count, required, met = purchase_order_service.approval_summary_for(
        db, po_id=po_id, workspace_id=workspace.id
    )
    return PurchaseOrderApproversList(
        approvers=[_approver_response(a, profile, position) for a, profile, position in rows],
        summary=ApprovalSummaryResponse(approved_count=approved_count, required=required, met=met),
    )


@router.post(
    "/{po_id}/approvers/",
    response_model=PurchaseOrderApproverResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Assign an approver to a purchase order"
)
def add_purchase_order_approver(
    po_id: int,
    body: PurchaseOrderApproverCreate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    record = purchase_order_service.add_approver(
        db, po_id=po_id, user_id=body.user_id,
        workspace_id=workspace.id, assigned_by=current_user.id
    )
    profile = profile_dao.get(db, id=record.user_id)
    member = workspace_member_dao.get_by_workspace_and_user(
        db, workspace_id=workspace.id, user_id=record.user_id
    )
    return _approver_response(record, profile, member.position if member else None)


@router.delete(
    "/{po_id}/approvers/{user_id}/",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove an approver from a purchase order"
)
def remove_purchase_order_approver(
    po_id: int,
    user_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    purchase_order_service.remove_approver(
        db, po_id=po_id, user_id=user_id, workspace_id=workspace.id, performed_by=current_user.id
    )


@router.post(
    "/{po_id}/approvers/me/approve/",
    response_model=PurchaseOrderApproverResponse,
    status_code=status.HTTP_200_OK,
    summary="Current user approves the purchase order"
)
def approve_purchase_order(
    po_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    record = purchase_order_service.set_approval(
        db, po_id=po_id, user_id=current_user.id, workspace_id=workspace.id, approved=True
    )
    member = workspace_member_dao.get_by_workspace_and_user(
        db, workspace_id=workspace.id, user_id=current_user.id
    )
    return _approver_response(record, current_user, member.position if member else None)


@router.delete(
    "/{po_id}/approvers/me/approve/",
    response_model=PurchaseOrderApproverResponse,
    status_code=status.HTTP_200_OK,
    summary="Current user withdraws their approval"
)
def unapprove_purchase_order(
    po_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    record = purchase_order_service.set_approval(
        db, po_id=po_id, user_id=current_user.id, workspace_id=workspace.id, approved=False
    )
    member = workspace_member_dao.get_by_workspace_and_user(
        db, workspace_id=workspace.id, user_id=current_user.id
    )
    return _approver_response(record, current_user, member.position if member else None)


# ─── Purchase Order Events ─────────────────────────────────────

@router.get(
    "/{po_id}/events/",
    response_model=List[PurchaseOrderEventResponse],
    status_code=status.HTTP_200_OK,
    summary="List purchase order activity events"
)
def list_purchase_order_events(
    po_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    rows = purchase_order_service.list_events(db, po_id=po_id, workspace_id=workspace.id)
    return [
        PurchaseOrderEventResponse(
            id=e.id,
            workspace_id=e.workspace_id,
            purchase_order_id=e.purchase_order_id,
            event_type=e.event_type,
            description=e.description,
            metadata=(
                PurchaseOrderEventMetadata.model_validate(e.metadata_json)
                if e.metadata_json
                else None
            ),
            performed_by=e.performed_by,
            user_name=profile.name if profile else None,
            created_at=e.created_at,
        )
        for e, profile in rows
    ]


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
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return purchase_order_service.add_item(
        db, po_id=po_id, item_in=item_in, workspace_id=workspace.id, user_id=current_user.id
    )


@router.post(
    "/{po_id}/items/sync/",
    response_model=PurchaseOrderResponse,
    status_code=status.HTTP_200_OK,
    summary="Sync purchase order items (batch add/update/remove)",
)
def sync_purchase_order_items(
    po_id: int,
    sync_in: PurchaseOrderItemSyncRequest,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return purchase_order_service.sync_items(
        db,
        po_id=po_id,
        sync_in=sync_in,
        workspace_id=workspace.id,
        user_id=current_user.id,
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
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return purchase_order_service.update_item(
        db, item_id=item_id, item_in=item_in, workspace_id=workspace.id, user_id=current_user.id
    )


@router.delete(
    "/items/{item_id}/",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove item from purchase order"
)
def remove_purchase_order_item(
    item_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    purchase_order_service.remove_item(
        db, item_id=item_id, workspace_id=workspace.id, user_id=current_user.id
    )
