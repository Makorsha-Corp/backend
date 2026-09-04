"""Attachment markup DAO — workspace-scoped overlay storage."""
from typing import List, Optional

from sqlalchemy.orm import Session

from app.dao.base import BaseDAO
from app.models.attachment_markup import AttachmentMarkup


class AttachmentMarkupDAO(BaseDAO[AttachmentMarkup, object, object]):
    """DAO for per-user attachment markup layers."""

    def get_for_attachment(
        self,
        db: Session,
        *,
        workspace_id: int,
        attachment_id: int,
    ) -> List[AttachmentMarkup]:
        return (
            db.query(AttachmentMarkup)
            .filter(
                AttachmentMarkup.workspace_id == workspace_id,
                AttachmentMarkup.attachment_id == attachment_id,
            )
            .order_by(AttachmentMarkup.updated_at.asc())
            .all()
        )

    def get_for_user(
        self,
        db: Session,
        *,
        workspace_id: int,
        attachment_id: int,
        user_id: int,
    ) -> Optional[AttachmentMarkup]:
        return (
            db.query(AttachmentMarkup)
            .filter(
                AttachmentMarkup.workspace_id == workspace_id,
                AttachmentMarkup.attachment_id == attachment_id,
                AttachmentMarkup.user_id == user_id,
            )
            .first()
        )

    def upsert_for_user(
        self,
        db: Session,
        *,
        workspace_id: int,
        attachment_id: int,
        user_id: int,
        payload: dict,
    ) -> AttachmentMarkup:
        row = self.get_for_user(
            db,
            workspace_id=workspace_id,
            attachment_id=attachment_id,
            user_id=user_id,
        )
        if row is None:
            row = AttachmentMarkup(
                workspace_id=workspace_id,
                attachment_id=attachment_id,
                user_id=user_id,
                payload=payload,
            )
            db.add(row)
        else:
            row.payload = payload
        db.flush()
        return row

    def delete_for_user(
        self,
        db: Session,
        *,
        workspace_id: int,
        attachment_id: int,
        user_id: int,
    ) -> bool:
        row = self.get_for_user(
            db,
            workspace_id=workspace_id,
            attachment_id=attachment_id,
            user_id=user_id,
        )
        if row is None:
            return False
        db.delete(row)
        db.flush()
        return True


attachment_markup_dao = AttachmentMarkupDAO(AttachmentMarkup)
