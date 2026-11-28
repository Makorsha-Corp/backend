"""DAO for attachment markup event audit log."""

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
    ) -> list[AttachmentMarkupEvent]:
        """Return every markup event of the attachment, newest first.

        No cap: the history is a log and is never trimmed. ``id`` breaks ties
        between entries written within the same clock tick.
        """
        return (
            db.query(AttachmentMarkupEvent)
            .filter(
                AttachmentMarkupEvent.workspace_id == workspace_id,
                AttachmentMarkupEvent.attachment_id == attachment_id,
            )
            .order_by(
                AttachmentMarkupEvent.created_at.desc(),
                AttachmentMarkupEvent.id.desc(),
            )
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
        session_id: str | None = None,
        metadata_json: dict | None = None,
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
