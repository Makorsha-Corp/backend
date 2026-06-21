"""Expense order API endpoints"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_workspace, get_current_active_user
from app.dao.profile import profile_dao
from app.dao.workspace_member import workspace_member_dao
from app.models.workspace import Workspace
from app.models.profile import Profile
from app.schemas.expense_order import (
    ExpenseOrderCreate, ExpenseOrderUpdate, ExpenseOrderResponse,
    ExpenseOrderItemCreate, ExpenseOrderItemUpdate, ExpenseOrderItemResponse,
    ExpenseOrderSectionConfirmRequest,
    ExpenseOrderApproverCreate, ExpenseOrderApproverResponse,
    ApprovalSummaryResponse, ExpenseOrderApproversList,
    ExpenseOrderEventMetadata, ExpenseOrderEventResponse,
)
from app.services.expense_order_service import expense_order_service


def _approver_response(record, profile=None, position=None) -> ExpenseOrderApproverResponse:
    return ExpenseOrderApproverResponse(
        id=record.id,
        workspace_id=record.workspace_id,
        expense_order_id=record.expense_order_id,
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
    'details': 'details_confirmed',
    'items': 'items_confirmed',
    'invoice': 'invoice_confirmed',
}


router = APIRouter()


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
    invoice_id: Optional[int] = Query(None),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    return expense_order_service.list_expense_orders(
        db, workspace_id=workspace.id,
        expense_category=expense_category, account_id=account_id, invoice_id=invoice_id,
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


@router.patch(
    "/{eo_id}/section-confirm/",
    response_model=ExpenseOrderResponse,
    status_code=status.HTTP_200_OK,
    summary="Confirm or unconfirm an expense order section",
)
def set_expense_order_section_confirm(
    eo_id: int,
    body: ExpenseOrderSectionConfirmRequest,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    confirm_field = _SECTION_CONFIRM_FIELDS[body.section]
    return expense_order_service.update_expense_order(
        db,
        eo_id=eo_id,
        eo_in=ExpenseOrderUpdate(**{confirm_field: body.confirmed}),
        workspace_id=workspace.id,
        user_id=current_user.id,
    )


@router.post(
    "/{eo_id}/complete/",
    response_model=ExpenseOrderResponse,
    status_code=status.HTTP_200_OK,
    summary="Mark expense order complete",
)
def mark_expense_order_complete(
    eo_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return expense_order_service.mark_order_complete(
        db,
        eo_id=eo_id,
        workspace_id=workspace.id,
        user_id=current_user.id,
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


# ─── Expense Order Approvers ───────────────────────────────────

@router.get(
    "/{eo_id}/approvers/",
    response_model=ExpenseOrderApproversList,
    status_code=status.HTTP_200_OK,
    summary="List expense order approvers + approval summary"
)
def list_expense_order_approvers(
    eo_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    rows = expense_order_service.list_approvers(db, eo_id=eo_id, workspace_id=workspace.id)
    approved_count, required, met = expense_order_service.approval_summary_for(
        db, eo_id=eo_id, workspace_id=workspace.id
    )
    return ExpenseOrderApproversList(
        approvers=[_approver_response(a, profile, position) for a, profile, position in rows],
        summary=ApprovalSummaryResponse(approved_count=approved_count, required=required, met=met),
    )


@router.post(
    "/{eo_id}/approvers/",
    response_model=ExpenseOrderApproverResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Assign an approver to an expense order"
)
def add_expense_order_approver(
    eo_id: int,
    body: ExpenseOrderApproverCreate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    record = expense_order_service.add_approver(
        db, eo_id=eo_id, user_id=body.user_id,
        workspace_id=workspace.id, assigned_by=current_user.id
    )
    profile = profile_dao.get(db, id=record.user_id)
    member = workspace_member_dao.get_by_workspace_and_user(
        db, workspace_id=workspace.id, user_id=record.user_id
    )
    return _approver_response(record, profile, member.position if member else None)


@router.delete(
    "/{eo_id}/approvers/{user_id}/",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove an approver from an expense order"
)
def remove_expense_order_approver(
    eo_id: int,
    user_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    expense_order_service.remove_approver(
        db, eo_id=eo_id, user_id=user_id,
        workspace_id=workspace.id, performed_by=current_user.id
    )


@router.post(
    "/{eo_id}/approvers/me/approve/",
    response_model=ExpenseOrderApproverResponse,
    status_code=status.HTTP_200_OK,
    summary="Approve expense order as current user"
)
def approve_expense_order(
    eo_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    record = expense_order_service.approve_as_me(
        db, eo_id=eo_id, user_id=current_user.id, workspace_id=workspace.id
    )
    member = workspace_member_dao.get_by_workspace_and_user(
        db, workspace_id=workspace.id, user_id=current_user.id
    )
    return _approver_response(record, current_user, member.position if member else None)


@router.delete(
    "/{eo_id}/approvers/me/approve/",
    response_model=ExpenseOrderApproverResponse,
    status_code=status.HTTP_200_OK,
    summary="Withdraw expense order approval as current user"
)
def unapprove_expense_order(
    eo_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    record = expense_order_service.unapprove_as_me(
        db, eo_id=eo_id, user_id=current_user.id, workspace_id=workspace.id
    )
    member = workspace_member_dao.get_by_workspace_and_user(
        db, workspace_id=workspace.id, user_id=current_user.id
    )
    return _approver_response(record, current_user, member.position if member else None)


# ─── Expense Order Events ──────────────────────────────────────

@router.get(
    "/{eo_id}/events/",
    response_model=List[ExpenseOrderEventResponse],
    status_code=status.HTTP_200_OK,
    summary="List expense order activity events"
)
def list_expense_order_events(
    eo_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    rows = expense_order_service.list_events(db, eo_id=eo_id, workspace_id=workspace.id)
    return [
        ExpenseOrderEventResponse(
            id=e.id,
            workspace_id=e.workspace_id,
            expense_order_id=e.expense_order_id,
            event_type=e.event_type,
            description=e.description,
            metadata=(
                ExpenseOrderEventMetadata.model_validate(e.metadata_json)
                if e.metadata_json
                else None
            ),
            performed_by=e.performed_by,
            user_name=profile.name if profile else None,
            created_at=e.created_at,
        )
        for e, profile in rows
    ]


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
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return expense_order_service.add_item(
        db, eo_id=eo_id, item_in=item_in, workspace_id=workspace.id, user_id=current_user.id
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
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return expense_order_service.update_item(
        db, item_id=item_id, item_in=item_in, workspace_id=workspace.id, user_id=current_user.id
    )


@router.delete(
    "/items/{item_id}/",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove item from expense order"
)
def remove_expense_order_item(
    item_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    expense_order_service.remove_item(
        db, item_id=item_id, workspace_id=workspace.id, user_id=current_user.id
    )
