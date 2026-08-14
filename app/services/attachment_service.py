"""Attachment service — transaction orchestration for upload workflows."""
from sqlalchemy.orm import Session

from app.core.config import settings
from app.managers.attachment_manager import (
    AttachmentConfirmError,
    AttachmentLimitError,
    AttachmentManager,
    AttachmentNotFoundError,
    AttachmentValidationError,
    attachment_manager,
)
from app.models.enums import AttachmentEntityTypeEnum
from app.models.profile import Profile
from app.models.workspace import Workspace
from app.schemas.attachment import (
    AttachmentConfirmRequest,
    AttachmentListResponse,
    AttachmentResponse,
    AttachmentSignRequest,
    AttachmentSignResponse,
)
from app.services.base_service import BaseService
from app.dao.attachment_link import attachment_link_dao


class AttachmentService(BaseService):
    """Service for attachment upload workflows."""

    def __init__(self) -> None:
        super().__init__()
        self.manager: AttachmentManager = attachment_manager

    def sign_upload(
        self,
        db: Session,
        *,
        workspace: Workspace,
        user: Profile,
        payload: AttachmentSignRequest,
    ) -> AttachmentSignResponse:
        try:
            normalized = self.manager.normalize_upload_request(payload)
            entity_label = self.manager.resolve_entity_label(
                db,
                workspace_id=workspace.id,
                entity_type=payload.entity_type,
                entity_id=payload.entity_id,
            )
            asset_folder = self.manager.build_asset_folder(
                workspace_name=workspace.name,
                entity_type=payload.entity_type,
                entity_label=entity_label,
            )
            public_id = self.manager.build_public_id(workspace_id=workspace.id)
            display_name = self.manager.build_display_name(normalized.file_name)
            attachment = self.manager.create_pending_attachment(
                db,
                workspace_id=workspace.id,
                user=user,
                payload=payload,
                normalized=normalized,
                stored_public_id=public_id,
                asset_folder=asset_folder,
            )
            response = self.manager.build_sign_response(
                attachment=attachment,
                public_id=public_id,
                asset_folder=asset_folder,
                display_name=display_name,
            )
            self._commit_transaction(db)
            db.refresh(attachment)
            return response
        except Exception:
            self._rollback_transaction(db)
            raise

    def confirm_upload(
        self,
        db: Session,
        *,
        workspace_id: int,
        attachment_id: int,
        performed_by: int | None = None,
        payload: AttachmentConfirmRequest | None = None,
    ) -> AttachmentResponse:
        try:
            attachment = self.manager.confirm_attachment(
                db,
                attachment_id=attachment_id,
                workspace_id=workspace_id,
                performed_by=performed_by,
                _payload=payload,
            )
            self._commit_transaction(db)
            db.refresh(attachment)
            return self.manager.to_response(db, attachment, workspace_id=workspace_id)
        except Exception:
            self._rollback_transaction(db)
            raise

    def list_attachments(
        self,
        db: Session,
        *,
        workspace_id: int,
        entity_type: AttachmentEntityTypeEnum,
        entity_id: int,
        skip: int = 0,
        limit: int = 100,
    ) -> AttachmentListResponse:
        attachments = attachment_link_dao.get_attachments_for_entity(
            db,
            workspace_id=workspace_id,
            entity_type=entity_type.value,
            entity_id=entity_id,
            skip=skip,
            limit=limit,
        )
        slot_count = attachment_link_dao.count_linked_attachments_for_entity(
            db,
            workspace_id=workspace_id,
            entity_type=entity_type.value,
            entity_id=entity_id,
        )
        return AttachmentListResponse(
            items=[
                self.manager.to_response(db, attachment, workspace_id=workspace_id)
                for attachment in attachments
            ],
            slot_count=slot_count,
            max_per_entity=settings.MAX_ATTACHMENTS_PER_ENTITY,
        )

    def get_attachment(
        self,
        db: Session,
        *,
        workspace_id: int,
        attachment_id: int,
    ) -> AttachmentResponse:
        from app.dao.attachment import attachment_dao

        attachment = attachment_dao.get_active(db, attachment_id, workspace_id)
        if not attachment:
            raise AttachmentNotFoundError(f"Attachment {attachment_id} not found.")
        return self.manager.to_response(db, attachment, workspace_id=workspace_id)

    def get_pdf_page_image(
        self,
        db: Session,
        *,
        workspace_id: int,
        attachment_id: int,
        page: int,
    ):
        from app.schemas.attachment import AttachmentPdfPageResponse

        payload = self.manager.get_pdf_page_image(
            db,
            attachment_id=attachment_id,
            workspace_id=workspace_id,
            page=page,
        )
        return AttachmentPdfPageResponse(**payload)

    def delete_attachment(
        self,
        db: Session,
        *,
        workspace_id: int,
        attachment_id: int,
        deleted_by: int,
    ) -> AttachmentResponse:
        try:
            attachment = self.manager.delete_attachment(
                db,
                attachment_id=attachment_id,
                workspace_id=workspace_id,
                deleted_by=deleted_by,
            )
            if not attachment:
                raise AttachmentNotFoundError(f"Attachment {attachment_id} not found.")
            self._commit_transaction(db)
            db.refresh(attachment)
            return self.manager.to_response(db, attachment, workspace_id=workspace_id)
        except Exception:
            self._rollback_transaction(db)
            raise


attachment_service = AttachmentService()

# Re-export for endpoints
__all__ = [
    "attachment_service",
    "AttachmentValidationError",
    "AttachmentNotFoundError",
    "AttachmentConfirmError",
]
