"""Help ticket business logic."""
from sqlalchemy.orm import Session

from app.dao.help_ticket import help_ticket_dao
from app.models.enums import HelpTicketStatusEnum
from app.models.help_ticket import HelpTicket
from app.schemas.help_ticket import HelpTicketCreate, HelpTicketUpdate
from app.utils.time import utcnow


class HelpTicketNotFoundError(LookupError):
    """Ticket not found in workspace."""


class HelpTicketManager:
    """Manager for help ticket workflows."""

    def get_by_id_and_workspace(
        self,
        session: Session,
        *,
        ticket_id: int,
        workspace_id: int,
    ) -> HelpTicket:
        ticket = help_ticket_dao.get_by_id_and_workspace(
            session, id=ticket_id, workspace_id=workspace_id
        )
        if ticket is None:
            raise HelpTicketNotFoundError("Help ticket not found.")
        return ticket

    def list_tickets(
        self,
        session: Session,
        *,
        workspace_id: int,
        status: HelpTicketStatusEnum | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[HelpTicket]:
        status_value = status.value if status is not None else None
        return help_ticket_dao.list_by_workspace(
            session,
            workspace_id=workspace_id,
            status=status_value,
            skip=skip,
            limit=limit,
        )

    def create_ticket(
        self,
        session: Session,
        *,
        workspace_id: int,
        user_id: int,
        payload: HelpTicketCreate,
    ) -> HelpTicket:
        return help_ticket_dao.create_with_user(
            session,
            obj_in=payload,
            workspace_id=workspace_id,
            user_id=user_id,
        )

    def update_ticket(
        self,
        session: Session,
        *,
        ticket: HelpTicket,
        payload: HelpTicketUpdate,
        user_id: int,
    ) -> HelpTicket:
        update_data = payload.model_dump(exclude_unset=True)
        new_status = update_data.pop("status", None)

        if new_status is not None:
            status_value = (
                new_status.value if isinstance(new_status, HelpTicketStatusEnum) else new_status
            )
            if status_value == HelpTicketStatusEnum.CLOSED.value:
                update_data["status"] = HelpTicketStatusEnum.CLOSED.value
                update_data["closed_at"] = utcnow()
                update_data["closed_by"] = user_id
            elif status_value == HelpTicketStatusEnum.OPEN.value:
                update_data["status"] = HelpTicketStatusEnum.OPEN.value
                update_data["closed_at"] = None
                update_data["closed_by"] = None

        return help_ticket_dao.update(session, db_obj=ticket, obj_in=update_data)


help_ticket_manager = HelpTicketManager()
