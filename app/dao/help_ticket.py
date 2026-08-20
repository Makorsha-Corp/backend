"""Help ticket DAO operations."""
from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session, joinedload

from app.dao.base import BaseDAO
from app.models.help_ticket import HelpTicket
from app.models.profile import Profile
from app.models.workspace import Workspace
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

    def get_by_id(
        self,
        db: Session,
        *,
        ticket_id: int,
    ) -> Optional[HelpTicket]:
        return (
            db.query(HelpTicket)
            .options(joinedload(HelpTicket.creator))
            .filter(HelpTicket.id == ticket_id)
            .first()
        )

    def get_by_id_and_workspace(
        self,
        db: Session,
        *,
        id: int,
        workspace_id: int,
    ) -> Optional[HelpTicket]:
        return (
            db.query(HelpTicket)
            .options(joinedload(HelpTicket.creator))
            .filter(HelpTicket.id == id, HelpTicket.workspace_id == workspace_id)
            .first()
        )

    def list_by_workspace(
        self,
        db: Session,
        *,
        workspace_id: int,
        status: Optional[str] = None,
        created_by: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[HelpTicket]:
        query = (
            db.query(HelpTicket)
            .options(joinedload(HelpTicket.creator))
            .filter(HelpTicket.workspace_id == workspace_id)
        )
        if status is not None:
            query = query.filter(HelpTicket.status == status)
        if created_by is not None:
            query = query.filter(HelpTicket.created_by == created_by)
        return (
            query.order_by(HelpTicket.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def list_platform(
        self,
        db: Session,
        *,
        status: Optional[str] = None,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Tuple[HelpTicket, str, Optional[str]]]:
        """Return (ticket, workspace_name, creator_name) across all workspaces."""
        query = (
            db.query(HelpTicket, Workspace.name, Profile.name)
            .options(joinedload(HelpTicket.creator))
            .join(Workspace, HelpTicket.workspace_id == Workspace.id)
            .outerjoin(Profile, HelpTicket.created_by == Profile.id)
        )
        if status is not None:
            query = query.filter(HelpTicket.status == status)
        if search:
            term = f"%{search.strip()}%"
            query = query.filter(
                (HelpTicket.title.ilike(term))
                | (HelpTicket.ticket_number.ilike(term))
                | (HelpTicket.description.ilike(term))
                | (Workspace.name.ilike(term))
            )
        rows = (
            query.order_by(HelpTicket.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return [(ticket, workspace_name, creator_name) for ticket, workspace_name, creator_name in rows]

    def get_platform_by_id(
        self,
        db: Session,
        *,
        ticket_id: int,
    ) -> Optional[Tuple[HelpTicket, str, Optional[str]]]:
        row = (
            db.query(HelpTicket, Workspace.name, Profile.name)
            .options(joinedload(HelpTicket.creator))
            .join(Workspace, HelpTicket.workspace_id == Workspace.id)
            .outerjoin(Profile, HelpTicket.created_by == Profile.id)
            .filter(HelpTicket.id == ticket_id)
            .first()
        )
        if row is None:
            return None
        ticket, workspace_name, creator_name = row
        return ticket, workspace_name, creator_name


help_ticket_dao = DAOHelpTicket(HelpTicket)
