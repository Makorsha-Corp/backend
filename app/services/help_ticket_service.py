"""Help ticket service — transaction orchestration."""
from typing import List

from sqlalchemy.orm import Session

from app.managers.help_ticket_manager import (
    HelpTicketForbiddenError,
    HelpTicketManager,
    HelpTicketNotFoundError,
    help_ticket_manager,
)
from app.models.enums import HelpTicketStatusEnum
from app.models.profile import Profile
from app.models.workspace import Workspace
from app.schemas.help_ticket import (
    HelpTicketCreate,
    HelpTicketResponse,
    HelpTicketUpdate,
    PlatformHelpTicketListItem,
)
from app.services.base_service import BaseService


class HelpTicketService(BaseService):
    """Service for help ticket CRUD."""

    def __init__(self) -> None:
        super().__init__()
        self.manager: HelpTicketManager = help_ticket_manager

    def create_ticket(
        self,
        db: Session,
        *,
        workspace: Workspace,
        user: Profile,
        payload: HelpTicketCreate,
    ) -> HelpTicketResponse:
        try:
            ticket = self.manager.create_ticket(
                db,
                workspace_id=workspace.id,
                user_id=user.id,
                payload=payload,
            )
            self._commit_transaction(db)
            db.refresh(ticket)
            from app.dao.help_ticket import help_ticket_dao

            refreshed = help_ticket_dao.get_by_id(db, ticket_id=ticket.id)
            return self.manager.to_response(refreshed or ticket)
        except Exception:
            self._rollback_transaction(db)
            raise

    def list_tickets(
        self,
        db: Session,
        *,
        workspace_id: int,
        user: Profile,
        role: str | None,
        status: HelpTicketStatusEnum | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[HelpTicketResponse]:
        tickets = self.manager.list_tickets(
            db,
            workspace_id=workspace_id,
            user=user,
            role=role,
            status=status,
            skip=skip,
            limit=limit,
        )
        return [self.manager.to_response(t) for t in tickets]

    def get_ticket(
        self,
        db: Session,
        *,
        workspace_id: int,
        ticket_id: int,
        user: Profile,
        role: str | None,
    ) -> HelpTicketResponse:
        ticket = self.manager.get_by_id_and_workspace(
            db,
            ticket_id=ticket_id,
            workspace_id=workspace_id,
            user=user,
            role=role,
        )
        return self.manager.to_response(ticket)

    def update_ticket(
        self,
        db: Session,
        *,
        workspace_id: int,
        ticket_id: int,
        user: Profile,
        role: str | None,
        payload: HelpTicketUpdate,
    ) -> HelpTicketResponse:
        try:
            ticket = self.manager.get_by_id_and_workspace(
                db,
                ticket_id=ticket_id,
                workspace_id=workspace_id,
                user=user,
                role=role,
            )
            ticket = self.manager.update_ticket(
                db, ticket=ticket, payload=payload, user_id=user.id
            )
            self._commit_transaction(db)
            db.refresh(ticket)
            from app.dao.help_ticket import help_ticket_dao

            refreshed = help_ticket_dao.get_by_id(db, ticket_id=ticket.id)
            return self.manager.to_response(refreshed or ticket)
        except Exception:
            self._rollback_transaction(db)
            raise

    def list_platform_tickets(
        self,
        db: Session,
        *,
        status: HelpTicketStatusEnum | None = None,
        search: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[PlatformHelpTicketListItem]:
        return self.manager.list_platform_tickets(
            db,
            status=status,
            search=search,
            skip=skip,
            limit=limit,
        )

    def get_platform_ticket(
        self,
        db: Session,
        *,
        ticket_id: int,
    ) -> PlatformHelpTicketListItem:
        return self.manager.get_platform_ticket(db, ticket_id=ticket_id)


help_ticket_service = HelpTicketService()
