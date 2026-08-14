"""Attachment link DAO operations"""
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.dao.base import BaseDAO
from app.models.attachment import Attachment
from app.models.attachment_link import AttachmentLink


class AttachmentLinkCreateSchema:
    """Minimal create payload for attachment links."""

    def __init__(
        self,
        *,
        workspace_id: int,
        attachment_id: int,
        entity_type: str,
        entity_id: int,
        linked_by: int,
    ):
        self.workspace_id = workspace_id
        self.attachment_id = attachment_id
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.linked_by = linked_by

    def model_dump(self) -> dict:
        return {
            "workspace_id": self.workspace_id,
            "attachment_id": self.attachment_id,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "linked_by": self.linked_by,
        }


class AttachmentLinkDAO(BaseDAO[AttachmentLink, AttachmentLinkCreateSchema, AttachmentLinkCreateSchema]):
    """DAO for polymorphic attachment links (workspace-scoped)."""

    def get_by_entity(
        self,
        db: Session,
        *,
        workspace_id: int,
        entity_type: str,
        entity_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> List[AttachmentLink]:
        return (
            db.query(AttachmentLink)
            .filter(
                and_(
                    AttachmentLink.workspace_id == workspace_id,
                    AttachmentLink.entity_type == entity_type,
                    AttachmentLink.entity_id == entity_id,
                )
            )
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_attachments_for_entity(
        self,
        db: Session,
        *,
        workspace_id: int,
        entity_type: str,
        entity_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> List[Attachment]:
        return (
            db.query(Attachment)
            .join(AttachmentLink, AttachmentLink.attachment_id == Attachment.id)
            .filter(
                and_(
                    AttachmentLink.workspace_id == workspace_id,
                    AttachmentLink.entity_type == entity_type,
                    AttachmentLink.entity_id == entity_id,
                    Attachment.is_deleted == False,
                    Attachment.upload_status == "ready",
                )
            )
            .order_by(Attachment.uploaded_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )


    def count_linked_attachments_for_entity(
        self,
        db: Session,
        *,
        workspace_id: int,
        entity_type: str,
        entity_id: int,
    ) -> int:
        """Count non-deleted attachments linked to entity (all upload statuses)."""
        return (
            db.query(Attachment)
            .join(AttachmentLink, AttachmentLink.attachment_id == Attachment.id)
            .filter(
                and_(
                    AttachmentLink.workspace_id == workspace_id,
                    AttachmentLink.entity_type == entity_type,
                    AttachmentLink.entity_id == entity_id,
                    Attachment.is_deleted == False,
                )
            )
            .count()
        )


    def get_links_for_attachment(
        self,
        db: Session,
        *,
        workspace_id: int,
        attachment_id: int,
    ) -> List[AttachmentLink]:
        return (
            db.query(AttachmentLink)
            .filter(
                and_(
                    AttachmentLink.workspace_id == workspace_id,
                    AttachmentLink.attachment_id == attachment_id,
                )
            )
            .all()
        )


attachment_link_dao = AttachmentLinkDAO(AttachmentLink)
