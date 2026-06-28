"""Invoice event DAO"""
from typing import List
from sqlalchemy.orm import Session

from app.dao.base import BaseDAO
from app.models.invoice_event import InvoiceEvent
from app.models.profile import Profile


class InvoiceEventDAO(BaseDAO[InvoiceEvent, dict, dict]):

    def create_event(
        self,
        db: Session,
        *,
        workspace_id: int,
        invoice_id: int,
        event_type: str,
        description: str,
        performed_by: int | None = None,
        metadata: dict | None = None,
    ) -> InvoiceEvent:
        event = InvoiceEvent(
            workspace_id=workspace_id,
            invoice_id=invoice_id,
            event_type=event_type,
            description=description,
            performed_by=performed_by,
            metadata_json=metadata,
        )
        db.add(event)
        db.flush()
        return event

    def get_by_invoice(self, db: Session, *, invoice_id: int, workspace_id: int) -> List[dict]:
        rows = (
            db.query(InvoiceEvent, Profile.name.label("performed_by_name"))
            .outerjoin(Profile, InvoiceEvent.performed_by == Profile.id)
            .filter(
                InvoiceEvent.invoice_id == invoice_id,
                InvoiceEvent.workspace_id == workspace_id,
            )
            .order_by(InvoiceEvent.created_at.desc())
            .all()
        )
        return [
            {
                "id": ev.id,
                "workspace_id": ev.workspace_id,
                "invoice_id": ev.invoice_id,
                "event_type": ev.event_type,
                "description": ev.description,
                "metadata_json": ev.metadata_json,
                "performed_by": ev.performed_by,
                "performed_by_name": name,
                "created_at": ev.created_at,
            }
            for ev, name in rows
        ]


invoice_event_dao = InvoiceEventDAO(InvoiceEvent)
