"""DAO for attachment markup event audit log."""
from typing import List, Optional

from sqlalchemy.orm import Session

from app.dao.base import BaseDAO
from app.models.attachment_markup_event import AttachmentMarkupEvent


class AttachmentMarkupEventDAO(BaseDAO[AttachmentMarkupEvent, object, object]):
    """Append-only markup events scoped to workspace + attachment."""

    def list_for_attachment(
        self,
        db: Session,
        *,
        workspace_id: int,
        attachment_id: int,
        limit: int = 200,
    ) -> List[AttachmentMarkupEvent]:
        return (
            db.query(AttachmentMarkupEvent)
            .filter(
                AttachmentMarkupEvent.workspace_id == workspace_id,
                AttachmentMarkupEvent.attachment_id == attachment_id,
            )
            .order_by(AttachmentMarkupEvent.created_at.desc())
            .limit(limit)
            .all()
        )

    def create_event(
        self,
        db: Session,
        *,
        workspace_id: int,
        attachment_id: int,
        user_id: int,
        event_type: str,
        description: str,
        session_id: Optional[str] = None,
        metadata_json: Optional[dict] = None,
    ) -> AttachmentMarkupEvent:
        row = AttachmentMarkupEvent(
            workspace_id=workspace_id,
            attachment_id=attachment_id,
            user_id=user_id,
            session_id=session_id,
            event_type=event_type,
            description=description,
            metadata_json=metadata_json,
        )
        db.add(row)
        db.flush()
        return row


attachment_markup_event_dao = AttachmentMarkupEventDAO(AttachmentMarkupEvent)
