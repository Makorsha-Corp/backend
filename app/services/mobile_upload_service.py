"""Mobile upload session service — transaction orchestration."""
from sqlalchemy.orm import Session

from app.core.cloudinary_client import CloudinaryNotConfiguredError
from app.managers.mobile_upload_session_manager import (
    MobileUploadSessionError,
    MobileUploadSessionManager,
    MobileUploadSessionNotFoundError,
    mobile_upload_session_manager,
)
from app.models.enums import AttachmentEntityTypeEnum
from app.models.profile import Profile
from app.models.workspace import Workspace
from app.schemas.attachment import AttachmentResponse
from app.schemas.mobile_upload import (
    MobileUploadPromoteRequest,
    MobileUploadPublicConfirmRequest,
    MobileUploadPublicSessionResponse,
    MobileUploadPublicSignRequest,
    MobileUploadPublicSignResponse,
    MobileUploadSessionCreateRequest,
    MobileUploadSessionCreateResponse,
    MobileUploadSessionResponse,
)
from app.services.base_service import BaseService
from app.utils.attachment_allowlist import AttachmentConfirmError, AttachmentValidationError


class MobileUploadService(BaseService):
    """Service for mobile QR upload workflows."""

    def __init__(self) -> None:
        super().__init__()
        self.manager: MobileUploadSessionManager = mobile_upload_session_manager

    def create_session(
        self,
        db: Session,
        *,
        workspace: Workspace,
        user: Profile,
        payload: MobileUploadSessionCreateRequest,
    ) -> MobileUploadSessionCreateResponse:
        try:
            session, raw_token = self.manager.create_session(
                db,
                workspace=workspace,
                user=user,
                entity_type=payload.entity_type,
                entity_id=payload.entity_id,
                entity_label=payload.entity_label,
            )
            response = self.manager.to_create_response(session, raw_token)
            self._commit_transaction(db)
            return response
        except Exception:
            self._rollback_transaction(db)
            raise

    def get_session(
        self,
        db: Session,
        *,
        workspace_id: int,
        user_id: int,
        session_id: int,
    ) -> MobileUploadSessionResponse:
        session = self.manager.get_for_creator(
            db,
            session_id=session_id,
            workspace_id=workspace_id,
            user_id=user_id,
        )
        return self.manager.to_session_response(session)

    def cancel_session(
        self,
        db: Session,
        *,
        workspace_id: int,
        user_id: int,
        session_id: int,
    ) -> MobileUploadSessionResponse:
        try:
            session = self.manager.get_for_creator(
                db,
                session_id=session_id,
                workspace_id=workspace_id,
                user_id=user_id,
            )
            session = self.manager.cancel_session(db, session=session)
            self._commit_transaction(db)
            return self.manager.to_session_response(session)
        except Exception:
            self._rollback_transaction(db)
            raise

    def promote_session(
        self,
        db: Session,
        *,
        workspace: Workspace,
        user: Profile,
        session_id: int,
        payload: MobileUploadPromoteRequest,
    ) -> AttachmentResponse:
        try:
            session = self.manager.get_for_creator(
                db,
                session_id=session_id,
                workspace_id=workspace.id,
                user_id=user.id,
            )
            attachment = self.manager.promote_to_attachment(
                db,
                session=session,
                workspace=workspace,
                user=user,
                file_name=payload.file_name,
                note=payload.note,
            )
            response = self.manager.attachment_mgr.to_response(
                db,
                attachment,
                workspace_id=workspace.id,
            )
            self._commit_transaction(db)
            return response
        except Exception:
            self._rollback_transaction(db)
            raise

    def get_public_session(
        self,
        db: Session,
        *,
        raw_token: str,
    ) -> MobileUploadPublicSessionResponse:
        session = self.manager.get_by_raw_token(db, raw_token=raw_token)
        return self.manager.to_public_response(session)

    def public_sign(
        self,
        db: Session,
        *,
        payload: MobileUploadPublicSignRequest,
    ) -> MobileUploadPublicSignResponse:
        try:
            session = self.manager.get_by_raw_token(db, raw_token=payload.token)
            from app.dao.workspace import workspace_dao

            workspace = workspace_dao.get(db, session.workspace_id)
            if not workspace:
                raise MobileUploadSessionNotFoundError("Upload session not found.")
            response = self.manager.sign_staging_upload(
                db,
                session=session,
                workspace=workspace,
                file_name=payload.file_name,
                mime_type=payload.mime_type,
                file_size=payload.file_size,
            )
            self._commit_transaction(db)
            return response
        except Exception:
            self._rollback_transaction(db)
            raise

    def public_confirm(
        self,
        db: Session,
        *,
        payload: MobileUploadPublicConfirmRequest,
    ) -> MobileUploadPublicSessionResponse:
        try:
            session = self.manager.get_by_raw_token(db, raw_token=payload.token)
            session = self.manager.confirm_staging_upload(db, session=session)
            self._commit_transaction(db)
            return self.manager.to_public_response(session)
        except Exception:
            self._rollback_transaction(db)
            raise


mobile_upload_service = MobileUploadService()

__all__ = [
    "mobile_upload_service",
    "MobileUploadSessionNotFoundError",
    "MobileUploadSessionError",
    "AttachmentValidationError",
    "AttachmentConfirmError",
    "CloudinaryNotConfiguredError",
]
