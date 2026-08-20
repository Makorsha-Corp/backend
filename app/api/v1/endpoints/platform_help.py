"""Platform admin help ticket inbox — cross-workspace."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_platform_admin
from app.managers.help_ticket_manager import HelpTicketNotFoundError
from app.models.enums import HelpTicketStatusEnum
from app.models.profile import Profile
from app.schemas.help_ticket import PlatformHelpTicketListItem
from app.services.help_ticket_service import help_ticket_service

router = APIRouter()


@router.get(
    "/help/tickets",
    response_model=List[PlatformHelpTicketListItem],
    summary="List help tickets across all workspaces (platform admin)",
)
def list_platform_help_tickets(
    status_filter: Optional[HelpTicketStatusEnum] = Query(None, alias="status"),
    search: Optional[str] = Query(None, max_length=200),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    _: Profile = Depends(get_platform_admin),
    db: Session = Depends(get_db),
):
    return help_ticket_service.list_platform_tickets(
        db,
        status=status_filter,
        search=search,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/help/tickets/{ticket_id}",
    response_model=PlatformHelpTicketListItem,
    summary="Get a help ticket with workspace context (platform admin)",
)
def get_platform_help_ticket(
    ticket_id: int,
    _: Profile = Depends(get_platform_admin),
    db: Session = Depends(get_db),
):
    try:
        return help_ticket_service.get_platform_ticket(db, ticket_id=ticket_id)
    except HelpTicketNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
