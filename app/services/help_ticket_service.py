"""Help ticket service — transaction orchestration."""
from typing import List

from sqlalchemy.orm import Session

from app.managers.help_ticket_manager import (
    HelpTicketManager,
    HelpTicketNotFoundError,
    help_ticket_manager,
)
from app.models.enums import HelpTicketStatusEnum
from app.models.profile import Profile
from app.models.workspace import Workspace
from app.schemas.help_ticket import HelpTicketCreate, HelpTicketResponse, HelpTicketUpdate
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
            return HelpTicketResponse.model_validate(ticket)
        except Exception:
            self._rollback_transaction(db)
            raise

    def list_tickets(
        self,
        db: Session,
        *,
        workspace_id: int,
        status: HelpTicketStatusEnum | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[HelpTicketResponse]:
        tickets = self.manager.list_tickets(
            db,
            workspace_id=workspace_id,
            status=status,
            skip=skip,
            limit=limit,
        )
        return [HelpTicketResponse.model_validate(t) for t in tickets]

    def get_ticket(
        self,
        db: Session,
        *,
        workspace_id: int,
        ticket_id: int,
    ) -> HelpTicketResponse:
        ticket = self.manager.get_by_id_and_workspace(
            db, ticket_id=ticket_id, workspace_id=workspace_id
        )
        return HelpTicketResponse.model_validate(ticket)

    def update_ticket(
        self,
        db: Session,
        *,
        workspace_id: int,
        ticket_id: int,
        user: Profile,
        payload: HelpTicketUpdate,
    ) -> HelpTicketResponse:
        try:
            ticket = self.manager.get_by_id_and_workspace(
                db, ticket_id=ticket_id, workspace_id=workspace_id
            )
            ticket = self.manager.update_ticket(
                db, ticket=ticket, payload=payload, user_id=user.id
            )
            self._commit_transaction(db)
            db.refresh(ticket)
            return HelpTicketResponse.model_validate(ticket)
        except Exception:
            self._rollback_transaction(db)
            raise


help_ticket_service = HelpTicketService()
