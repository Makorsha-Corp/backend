"""Notification service — owns commit/rollback for notification writes."""
from __future__ import annotations
from typing import List, Tuple

from sqlalchemy.orm import Session

from app.dao.notification import notification_dao
from app.models.notification import Notification
from app.schemas.notification import MarkReadRequest


class NotificationService:
    def list_for_user(
        self,
        db: Session,
        workspace_id: int,
        user_id: int,
        unread_only: bool = False,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[Notification], int, int]:
        return notification_dao.get_for_user(
            db, workspace_id, user_id, unread_only, skip, limit
        )

    def mark_read(
        self,
        db: Session,
        workspace_id: int,
        user_id: int,
        data: MarkReadRequest,
    ) -> int:
        count = notification_dao.mark_read(db, workspace_id, user_id, data.ids)
        db.commit()
        return count

    def fan_out_mentions(
        self,
        db: Session,
        workspace_id: int,
        actor_user_id: int,
        mentioned_user_ids: List[int],
        entity_type: str,
        entity_id: int,
        source_id: int,
        preview: str | None = None,
    ) -> None:
        """Called inside discussion_service.create — db.commit() is owned by the caller."""
        for uid in set(mentioned_user_ids):
            if uid == actor_user_id:
                continue  # don't notify yourself
            notification_dao.create(
                db=db,
                workspace_id=workspace_id,
                recipient_user_id=uid,
                actor_user_id=actor_user_id,
                notification_type="mention",
                entity_type=entity_type,
                entity_id=entity_id,
                source_type="discussion",
                source_id=source_id,
                preview=preview,
            )


notification_service = NotificationService()
