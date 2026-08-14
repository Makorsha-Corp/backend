"""Help ticket DAO operations."""
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from app.dao.base import BaseDAO
from app.models.help_ticket import HelpTicket
from app.schemas.help_ticket import HelpTicketCreate, HelpTicketUpdate


class DAOHelpTicket(BaseDAO[HelpTicket, HelpTicketCreate, HelpTicketUpdate]):
    """DAO for HelpTicket model."""

    def generate_ticket_number(
        self, db: Session, *, workspace_id: int, year: int
    ) -> str:
        """Generate next ticket number: HELP-{year}-{sequence}."""
        prefix = f"HELP-{year}-"
        count = (
            db.query(HelpTicket)
            .filter(
                HelpTicket.workspace_id == workspace_id,
                HelpTicket.ticket_number.like(f"{prefix}%"),
            )
            .count()
        )
        return f"{prefix}{count + 1:03d}"

    def create_with_user(
        self,
        db: Session,
        *,
        obj_in: HelpTicketCreate,
        workspace_id: int,
        user_id: int,
    ) -> HelpTicket:
        current_year = datetime.now().year
        ticket_number = self.generate_ticket_number(
            db, workspace_id=workspace_id, year=current_year
        )
        db_obj = HelpTicket(
            **obj_in.model_dump(),
            workspace_id=workspace_id,
            ticket_number=ticket_number,
            created_by=user_id,
            status="open",
        )
        db.add(db_obj)
        db.flush()
        return db_obj

    def list_by_workspace(
        self,
        db: Session,
        *,
        workspace_id: int,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[HelpTicket]:
        query = db.query(HelpTicket).filter(HelpTicket.workspace_id == workspace_id)
        if status is not None:
            query = query.filter(HelpTicket.status == status)
        return (
            query.order_by(HelpTicket.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )


help_ticket_dao = DAOHelpTicket(HelpTicket)
