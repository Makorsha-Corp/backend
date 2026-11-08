"""Help ticket event DAO. SECURITY: All queries MUST filter by workspace_id."""
from typing import List

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.dao.base import BaseDAO
from app.models.help_ticket_event import HelpTicketEvent


class HelpTicketEventDAO(BaseDAO[HelpTicketEvent, object, object]):
    def get_by_ticket(
        self,
        db: Session,
        *,
        help_ticket_id: int,
        workspace_id: int,
    ) -> List[HelpTicketEvent]:
        return (
            db.query(HelpTicketEvent)
            .filter(
                HelpTicketEvent.help_ticket_id == help_ticket_id,
                HelpTicketEvent.workspace_id == workspace_id,
            )
            .order_by(desc(HelpTicketEvent.created_at), desc(HelpTicketEvent.id))
            .all()
        )


help_ticket_event_dao = HelpTicketEventDAO(HelpTicketEvent)
