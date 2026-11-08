"""Discussion service — owns commit/rollback and mention fan-out."""
from __future__ import annotations
import re
from typing import List, Tuple

from sqlalchemy.orm import Session

from app.dao.discussion import discussion_dao
from app.dao.help_ticket import help_ticket_dao
from app.models.discussion import Discussion
from app.models.enums import DiscussionEntityType, HelpTicketStatusEnum
from app.schemas.discussion import DiscussionCreate
from app.core.exceptions import APIException, NotFoundError, ValidationError
from fastapi import status


# Matches @[123] tokens where 123 is a user profile id
_MENTION_RE = re.compile(r"@\[(\d+)\]")


def _extract_mentions(message: str) -> List[int]:
    return [int(uid) for uid in _MENTION_RE.findall(message)]


class DiscussionService:
    def list(
        self,
        db: Session,
        workspace_id: int,
        entity_type: DiscussionEntityType,
        entity_id: int,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[Discussion], int]:
        return discussion_dao.get_by_entity(
            db, workspace_id, entity_type.value, entity_id, skip, limit
        )

    def create(
        self,
        db: Session,
        workspace_id: int,
        user_id: int,
        data: DiscussionCreate,
    ) -> Discussion:
        # Validate reply depth — only one level allowed
        if data.parent_id is not None:
            parent = discussion_dao.get_by_id(db, data.parent_id, workspace_id)
            if parent is None:
                raise APIException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Parent discussion not found",
                )
            if parent.parent_id is not None:
                raise APIException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Replies can only be one level deep",
                )
            # Reply must be on the same entity
            if parent.entity_type != data.entity_type.value or parent.entity_id != data.entity_id:
                raise APIException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Reply must be on the same entity as the parent",
                )

        if data.entity_type == DiscussionEntityType.support_ticket:
            ticket = help_ticket_dao.get_by_id_and_workspace(
                db,
                id=data.entity_id,
                workspace_id=workspace_id,
            )
            if ticket is None:
                raise NotFoundError("Help ticket not found")
            if ticket.status == HelpTicketStatusEnum.CLOSED.value:
                raise ValidationError("Cannot post on a closed ticket.")

        discussion = discussion_dao.create(
            db=db,
            workspace_id=workspace_id,
            entity_type=data.entity_type.value,
            entity_id=data.entity_id,
            user_id=user_id,
            message=data.message,
            parent_id=data.parent_id,
        )

        from app.services.notification_service import humanize_mention_preview

        if data.entity_type == DiscussionEntityType.support_ticket:
            from app.managers.help_ticket_manager import help_ticket_manager

            preview = humanize_mention_preview(db, data.message, max_len=120).strip()
            is_reply = data.parent_id is not None
            if preview:
                description = f"{'Replied' if is_reply else 'Posted'}: {preview}"
            else:
                description = "Replied in discussion" if is_reply else "Posted a message"
            help_ticket_manager.log_event(
                db,
                data.entity_id,
                workspace_id,
                "discussion_reply" if is_reply else "discussion_message",
                description,
                user_id,
                {
                    "discussion_id": discussion.id,
                    "parent_id": data.parent_id,
                    "preview": preview or None,
                },
            )

        # Fan out mention notifications (deferred import avoids circular deps)
        mentioned_ids = _extract_mentions(data.message)
        if mentioned_ids:
            from app.services.notification_service import notification_service

            notification_service.fan_out_mentions(
                db=db,
                workspace_id=workspace_id,
                actor_user_id=user_id,
                mentioned_user_ids=mentioned_ids,
                entity_type=data.entity_type.value,
                entity_id=data.entity_id,
                source_id=discussion.id,
                preview=humanize_mention_preview(db, data.message),
            )

        db.commit()
        db.refresh(discussion)
        return discussion


discussion_service = DiscussionService()
