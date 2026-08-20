"""Help ticket API — workspace-scoped support requests."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_active_user, get_current_workspace, get_db
from app.dao.workspace_member import workspace_member_dao
from app.managers.help_ticket_manager import HelpTicketForbiddenError, HelpTicketNotFoundError
from app.models.enums import HelpTicketStatusEnum
from app.models.profile import Profile
from app.models.workspace import Workspace
from app.schemas.help_ticket import HelpTicketCreate, HelpTicketResponse, HelpTicketUpdate
from app.services.help_ticket_service import help_ticket_service

router = APIRouter()


def _workspace_role(db: Session, *, workspace_id: int, user_id: int) -> str | None:
    membership = workspace_member_dao.get_by_workspace_and_user(
        db, workspace_id=workspace_id, user_id=user_id
    )
    return membership.role if membership else None


@router.post(
    "/tickets",
    response_model=HelpTicketResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a help ticket",
)
def create_help_ticket(
    payload: HelpTicketCreate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return help_ticket_service.create_ticket(
        db, workspace=workspace, user=current_user, payload=payload
    )


@router.get(
    "/tickets",
    response_model=List[HelpTicketResponse],
    summary="List workspace help tickets",
)
def list_help_tickets(
    status_filter: Optional[HelpTicketStatusEnum] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    role = _workspace_role(db, workspace_id=workspace.id, user_id=current_user.id)
    return help_ticket_service.list_tickets(
        db,
        workspace_id=workspace.id,
        user=current_user,
        role=role,
        status=status_filter,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/tickets/{ticket_id}",
    response_model=HelpTicketResponse,
    summary="Get a help ticket",
)
def get_help_ticket(
    ticket_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    role = _workspace_role(db, workspace_id=workspace.id, user_id=current_user.id)
    try:
        return help_ticket_service.get_ticket(
            db,
            workspace_id=workspace.id,
            ticket_id=ticket_id,
            user=current_user,
            role=role,
        )
    except HelpTicketNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except HelpTicketForbiddenError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.patch(
    "/tickets/{ticket_id}",
    response_model=HelpTicketResponse,
    summary="Update or close/reopen a help ticket",
)
def update_help_ticket(
    ticket_id: int,
    payload: HelpTicketUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    role = _workspace_role(db, workspace_id=workspace.id, user_id=current_user.id)
    try:
        return help_ticket_service.update_ticket(
            db,
            workspace_id=workspace.id,
            ticket_id=ticket_id,
            user=current_user,
            role=role,
            payload=payload,
        )
    except HelpTicketNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except HelpTicketForbiddenError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
