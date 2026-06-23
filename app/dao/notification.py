"""Notification DAO. SECURITY: All queries MUST filter by workspace_id."""
from __future__ import annotations
import json
from datetime import datetime
from typing import List, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session, joinedload

from app.core.notification_channels import NOTIFICATION_CHANNEL
from app.models.notification import Notification


class NotificationDAO:
    def get_for_user(
        self,
        db: Session,
        workspace_id: int,
        user_id: int,
        unread_only: bool = False,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[Notification], int, int]:
        base = db.query(Notification).filter(
            Notification.workspace_id == workspace_id,
            Notification.recipient_user_id == user_id,
        )
        if unread_only:
            base = base.filter(Notification.is_read.is_(False))

        total        = base.count()
        unread_count = db.query(Notification).filter(
            Notification.workspace_id == workspace_id,
            Notification.recipient_user_id == user_id,
            Notification.is_read.is_(False),
        ).count()

        items = (
            base.options(joinedload(Notification.actor))
            .order_by(Notification.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return items, total, unread_count

    def create(
        self,
        db: Session,
        workspace_id: int,
        recipient_user_id: int,
        actor_user_id: int,
        notification_type: str,
        entity_type: str,
        entity_id: int,
        source_type: str,
        source_id: int,
        preview: str | None = None,
    ) -> Notification:
        obj = Notification(
            workspace_id=workspace_id,
            recipient_user_id=recipient_user_id,
            actor_user_id=actor_user_id,
            notification_type=notification_type,
            entity_type=entity_type,
            entity_id=entity_id,
            source_type=source_type,
            source_id=source_id,
            preview=preview,
        )
        db.add(obj)
        db.flush()
        payload = json.dumps(
            {
                "recipient_user_id": recipient_user_id,
                "workspace_id": workspace_id,
                "notification_id": obj.id,
            }
        )
        db.execute(
            text("SELECT pg_notify(:channel, :payload)"),
            {"channel": NOTIFICATION_CHANNEL, "payload": payload},
        )
        return obj

    def mark_read(
        self,
        db: Session,
        workspace_id: int,
        user_id: int,
        ids: List[int] | None = None,
    ) -> int:
        q = db.query(Notification).filter(
            Notification.workspace_id == workspace_id,
            Notification.recipient_user_id == user_id,
            Notification.is_read.is_(False),
        )
        if ids:
            q = q.filter(Notification.id.in_(ids))
        count = q.update({"is_read": True, "read_at": datetime.utcnow()}, synchronize_session=False)
        return count


notification_dao = NotificationDAO()
