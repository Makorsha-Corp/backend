"""Business logic for attachment markup overlay layers."""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy.orm import Session

from app.dao.attachment import attachment_dao
from app.dao.attachment_markup import attachment_markup_dao
from app.dao.profile import profile_dao
from app.managers.attachment_manager import (
    AttachmentNotFoundError,
    AttachmentValidationError,
)
from app.models.attachment import Attachment
from app.models.enums import UploadStatusEnum
from app.schemas.attachment_markup import (
    AttachmentMarkupLayerResponse,
    MarkupPayload,
    is_markup_payload_empty,
)


class AttachmentMarkupManager:
    """Per-user vector markup on ready image/PDF attachments."""

    MARKUP_UNAVAILABLE_MSG = "Markup is only available for images and PDFs."

    def _get_ready_attachment(
        self,
        session: Session,
        *,
        workspace_id: int,
        attachment_id: int,
    ) -> Attachment:
        attachment = attachment_dao.get_active(session, attachment_id, workspace_id)
        if not attachment:
            raise AttachmentNotFoundError(f"Attachment {attachment_id} not found.")
        if attachment.upload_status != UploadStatusEnum.READY.value:
            raise AttachmentValidationError(self.MARKUP_UNAVAILABLE_MSG)
        if not self._is_markupable(attachment):
            raise AttachmentValidationError(self.MARKUP_UNAVAILABLE_MSG)
        return attachment

    @staticmethod
    def _is_markupable(attachment: Attachment) -> bool:
        mime = attachment.mime_type or ""
        fmt = (attachment.format or "").lower()
        if mime == "application/pdf" or fmt == "pdf":
            return True
        return mime.startswith("image/")

    def _resolve_user_name(self, session: Session, user_id: int) -> str:
        profile = profile_dao.get(session, id=user_id)
        return profile.name if profile else f"User #{user_id}"

    def _to_layer_response(
        self,
        session: Session,
        *,
        row,
        current_user_id: int,
    ) -> AttachmentMarkupLayerResponse:
        payload = MarkupPayload.model_validate(row.payload)
        return AttachmentMarkupLayerResponse(
            user_id=row.user_id,
            user_name=self._resolve_user_name(session, row.user_id),
            is_mine=row.user_id == current_user_id,
            updated_at=row.updated_at,
            payload=payload,
        )

    def list_layers(
        self,
        session: Session,
        *,
        workspace_id: int,
        attachment_id: int,
        current_user_id: int,
    ) -> List[AttachmentMarkupLayerResponse]:
        self._get_ready_attachment(
            session, workspace_id=workspace_id, attachment_id=attachment_id
        )
        rows = attachment_markup_dao.get_for_attachment(
            session, workspace_id=workspace_id, attachment_id=attachment_id
        )
        return [
            self._to_layer_response(session, row=row, current_user_id=current_user_id)
            for row in rows
        ]

    def put_own_layer(
        self,
        session: Session,
        *,
        workspace_id: int,
        attachment_id: int,
        user_id: int,
        payload: MarkupPayload,
    ) -> Optional[AttachmentMarkupLayerResponse]:
        self._get_ready_attachment(
            session, workspace_id=workspace_id, attachment_id=attachment_id
        )
        if is_markup_payload_empty(payload):
            attachment_markup_dao.delete_for_user(
                session,
                workspace_id=workspace_id,
                attachment_id=attachment_id,
                user_id=user_id,
            )
            return None

        row = attachment_markup_dao.upsert_for_user(
            session,
            workspace_id=workspace_id,
            attachment_id=attachment_id,
            user_id=user_id,
            payload=payload.model_dump(),
        )
        session.refresh(row)
        return self._to_layer_response(session, row=row, current_user_id=user_id)

    def delete_own_layer(
        self,
        session: Session,
        *,
        workspace_id: int,
        attachment_id: int,
        user_id: int,
    ) -> None:
        self._get_ready_attachment(
            session, workspace_id=workspace_id, attachment_id=attachment_id
        )
        attachment_markup_dao.delete_for_user(
            session,
            workspace_id=workspace_id,
            attachment_id=attachment_id,
            user_id=user_id,
        )


attachment_markup_manager = AttachmentMarkupManager()
