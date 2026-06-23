"""Notification service — owns commit/rollback for notification writes."""
from __future__ import annotations

import re
from typing import List, Set, Tuple

from sqlalchemy.orm import Session

from app.dao.notification import notification_dao
from app.dao.workspace_member import workspace_member_dao
from app.models.notification import Notification
from app.models.profile import Profile
from app.schemas.notification import MarkReadRequest

_MENTION_RE = re.compile(r"@\[(\d+)\]")


def humanize_mention_preview(db: Session, message: str, max_len: int = 200) -> str:
    """Replace @[profile_id] tokens with @DisplayName for notification previews."""
    text = message[:max_len]
    user_ids = {int(match) for match in _MENTION_RE.findall(text)}
    if not user_ids:
        return text

    profiles = db.query(Profile).filter(Profile.id.in_(user_ids)).all()
    names = {profile.id: profile.name for profile in profiles}

    def repl(match: re.Match[str]) -> str:
        uid = int(match.group(1))
        return f"@{names.get(uid, f'User {uid}')}"

    return _MENTION_RE.sub(repl, text)


def _active_workspace_member_ids(db: Session, workspace_id: int) -> Set[int]:
    members = workspace_member_dao.get_workspace_members(
        db, workspace_id=workspace_id, status="active"
    )
    return {member.user_id for member in members}


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
        allowed_recipients = _active_workspace_member_ids(db, workspace_id)

        for uid in set(mentioned_user_ids):
            if uid not in allowed_recipients:
                continue
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
