"""Help ticket business logic."""
from sqlalchemy.orm import Session

from app.dao.help_ticket import help_ticket_dao
from app.models.enums import HelpTicketStatusEnum, HelpTicketTypeEnum, RoleEnum
from app.models.help_ticket import HelpTicket
from app.models.profile import Profile
from app.schemas.help_ticket import (
    HelpTicketCreate,
    HelpTicketResponse,
    HelpTicketUpdate,
    PlatformHelpTicketListItem,
)
from app.utils.time import utcnow

TICKET_VIEW_ALL_ROLES = {
    RoleEnum.OWNER.value,
    RoleEnum.GROUND_TEAM_MANAGER.value,
}


class HelpTicketNotFoundError(LookupError):
    """Ticket not found in workspace."""


class HelpTicketForbiddenError(PermissionError):
    """Caller may not access this ticket."""


class HelpTicketStatusChangeForbiddenError(PermissionError):
    """Caller may not change ticket status."""


class HelpTicketInvalidTransitionError(ValueError):
    """Requested status transition is not allowed."""


ALLOWED_STATUS_TRANSITIONS: dict[HelpTicketStatusEnum, set[HelpTicketStatusEnum]] = {
    HelpTicketStatusEnum.PENDING: {HelpTicketStatusEnum.OPENED},
    HelpTicketStatusEnum.OPENED: {HelpTicketStatusEnum.CLOSED},
    HelpTicketStatusEnum.CLOSED: {HelpTicketStatusEnum.OPENED},
}


class HelpTicketManager:
    """Manager for help ticket workflows."""

    @staticmethod
    def can_view_all_tickets(role: str | None) -> bool:
        return role in TICKET_VIEW_ALL_ROLES

    @staticmethod
    def can_access_ticket(
        *,
        ticket: HelpTicket,
        user: Profile,
        role: str | None,
    ) -> bool:
        if getattr(user, "is_platform_admin", False):
            return True
        if HelpTicketManager.can_view_all_tickets(role):
            return True
        return ticket.created_by == user.id

    def get_by_id_and_workspace(
        self,
        session: Session,
        *,
        ticket_id: int,
        workspace_id: int,
        user: Profile,
        role: str | None,
    ) -> HelpTicket:
        ticket = help_ticket_dao.get_by_id_and_workspace(
            session, id=ticket_id, workspace_id=workspace_id
        )
        if ticket is None:
            raise HelpTicketNotFoundError("Help ticket not found.")
        if not self.can_access_ticket(ticket=ticket, user=user, role=role):
            raise HelpTicketForbiddenError("You do not have access to this help ticket.")
        return ticket

    def list_tickets(
        self,
        session: Session,
        *,
        workspace_id: int,
        user: Profile,
        role: str | None,
        status: HelpTicketStatusEnum | None = None,
        ticket_type: HelpTicketTypeEnum | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[HelpTicket]:
        status_value = status.value if status is not None else None
        type_value = ticket_type.value if ticket_type is not None else None
        created_by_filter = None
        if not self.can_view_all_tickets(role):
            created_by_filter = user.id
        return help_ticket_dao.list_by_workspace(
            session,
            workspace_id=workspace_id,
            status=status_value,
            ticket_type=type_value,
            created_by=created_by_filter,
            skip=skip,
            limit=limit,
        )

    def list_platform_tickets(
        self,
        session: Session,
        *,
        status: HelpTicketStatusEnum | None = None,
        ticket_type: HelpTicketTypeEnum | None = None,
        search: str | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[PlatformHelpTicketListItem]:
        status_value = status.value if status is not None else None
        type_value = ticket_type.value if ticket_type is not None else None
        rows = help_ticket_dao.list_platform(
            session,
            status=status_value,
            ticket_type=type_value,
            search=search,
            skip=skip,
            limit=limit,
        )
        return [self._to_platform_item(ticket, workspace_name, creator_name) for ticket, workspace_name, creator_name in rows]

    def get_platform_ticket(
        self,
        session: Session,
        *,
        ticket_id: int,
    ) -> PlatformHelpTicketListItem:
        row = help_ticket_dao.get_platform_by_id(session, ticket_id=ticket_id)
        if row is None:
            raise HelpTicketNotFoundError("Help ticket not found.")
        ticket, workspace_name, creator_name = row
        return self._to_platform_item(ticket, workspace_name, creator_name)

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
        is_platform_admin: bool = False,
    ) -> HelpTicket:
        update_data = payload.model_dump(exclude_unset=True)
        new_status = update_data.pop("status", None)

        if new_status is not None:
            if not is_platform_admin:
                raise HelpTicketStatusChangeForbiddenError(
                    "Only platform admins may change ticket status."
                )
            target_status = (
                new_status
                if isinstance(new_status, HelpTicketStatusEnum)
                else HelpTicketStatusEnum(new_status)
            )
            try:
                current_status = HelpTicketStatusEnum(ticket.status)
            except ValueError as exc:
                raise HelpTicketInvalidTransitionError(
                    f"Cannot transition from invalid status '{ticket.status}'."
                ) from exc
            allowed = ALLOWED_STATUS_TRANSITIONS.get(current_status, set())
            if target_status not in allowed:
                raise HelpTicketInvalidTransitionError(
                    f"Cannot transition from {current_status.value} to {target_status.value}."
                )
            update_data["status"] = target_status.value
            if target_status == HelpTicketStatusEnum.CLOSED:
                update_data["closed_at"] = utcnow()
                update_data["closed_by"] = user_id
            elif (
                target_status == HelpTicketStatusEnum.OPENED
                and current_status == HelpTicketStatusEnum.CLOSED
            ):
                update_data["closed_at"] = None
                update_data["closed_by"] = None

        return help_ticket_dao.update(session, db_obj=ticket, obj_in=update_data)

    @staticmethod
    def to_response(ticket: HelpTicket) -> HelpTicketResponse:
        creator_name = ticket.creator.name if getattr(ticket, "creator", None) else None
        data = HelpTicketResponse.model_validate(ticket)
        if creator_name is not None:
            return data.model_copy(update={"creator_name": creator_name})
        return data

    @staticmethod
    def _to_platform_item(
        ticket: HelpTicket,
        workspace_name: str,
        creator_name: str | None,
    ) -> PlatformHelpTicketListItem:
        base = HelpTicketManager.to_response(ticket)
        return PlatformHelpTicketListItem(
            **{
                **base.model_dump(),
                "workspace_name": workspace_name,
                "creator_name": creator_name or base.creator_name,
            }
        )


help_ticket_manager = HelpTicketManager()
