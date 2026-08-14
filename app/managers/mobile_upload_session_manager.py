"""Mobile upload session business logic — QR token, Cloudinary staging."""
from __future__ import annotations

import secrets
import time
import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.core.cloudinary_client import (
    AUTHENTICATED_DELIVERY_TYPE,
    CloudinaryNotConfiguredError,
    build_signed_delivery_url,
    destroy_resource,
    generate_upload_signature,
    get_resource,
    rename_resource,
    update_resource_metadata,
)
from app.core.config import settings
from app.core.security import hash_refresh_token
from app.dao.mobile_upload_session import mobile_upload_session_dao
from app.managers.attachment_manager import AttachmentManager, attachment_manager
from app.models.enums import AttachmentEntityTypeEnum, MobileUploadSessionStatusEnum
from app.models.mobile_upload_session import MobileUploadSession
from app.models.profile import Profile
from app.models.workspace import Workspace
from app.models.attachment import Attachment
from app.schemas.attachment import AttachmentSignRequest
from app.schemas.mobile_upload import (
    MobileUploadPublicSignResponse,
    MobileUploadSessionCreateResponse,
    MobileUploadSessionResponse,
    MobileUploadPublicSessionResponse,
)
from app.utils.attachment_allowlist import (
    MAX_FILE_SIZE_BYTES,
    AttachmentConfirmError,
    AttachmentValidationError,
    sanitize_file_name,
    validate_cloudinary_resource,
)
from app.utils.time import utcnow

MOBILE_UPLOAD_TOKEN_BYTES = 32
SESSION_TTL_MINUTES = 10


def _naive_utc(value: datetime) -> datetime:
    """Match app `utcnow()` — DB timestamptz may come back timezone-aware."""
    if value.tzinfo is not None:
        return value.replace(tzinfo=None)
    return value


class MobileUploadSessionNotFoundError(LookupError):
    """Session missing, expired, or token invalid."""


class MobileUploadSessionError(ValueError):
    """Business rule violation on mobile upload session."""


class MobileUploadSessionManager:
    """Manager for QR phone upload staging sessions."""

    def __init__(self, attachment_mgr: AttachmentManager | None = None) -> None:
        self.attachment_mgr = attachment_mgr or attachment_manager

    def _hash_token(self, raw_token: str) -> str:
        return hash_refresh_token(raw_token)

    def _upload_env(self) -> str:
        return settings.CLOUDINARY_UPLOAD_ENV or settings.ENVIRONMENT

    def _is_production(self) -> bool:
        return self._upload_env() == "production"

    def build_staging_public_id(self, *, workspace_id: int, session_id: int) -> str:
        token = uuid.uuid4().hex
        base = f"ws-{workspace_id}/mobile-staging/{session_id}/{token}"
        if self._is_production():
            return base
        return f"{self._upload_env()}/{base}"

    def build_staging_asset_folder(self, *, workspace_name: str, session_id: int) -> str:
        folder = f"{workspace_name}/Mobile Staging/session-{session_id}"
        if self._is_production():
            return folder
        return f"Dev/{folder}"

    def create_session_token(self) -> tuple[str, str]:
        raw = secrets.token_urlsafe(MOBILE_UPLOAD_TOKEN_BYTES)
        return raw, self._hash_token(raw)

    def resolve_entity_label(
        self,
        session: Session,
        *,
        workspace: Workspace,
        entity_type: AttachmentEntityTypeEnum,
        entity_id: int,
        entity_label: str | None,
    ) -> str | None:
        if entity_label and entity_label.strip():
            return entity_label.strip()[:80]
        return self.attachment_mgr.resolve_entity_label(
            session,
            workspace_id=workspace.id,
            entity_type=entity_type,
            entity_id=entity_id,
        )

    def create_session(
        self,
        db: Session,
        *,
        workspace: Workspace,
        user: Profile,
        entity_type: AttachmentEntityTypeEnum,
        entity_id: int,
        entity_label: str | None,
    ) -> tuple[MobileUploadSession, str]:
        raw_token, token_hash = self.create_session_token()
        label = self.resolve_entity_label(
            db,
            workspace=workspace,
            entity_type=entity_type,
            entity_id=entity_id,
            entity_label=entity_label,
        )
        expires_at = utcnow() + timedelta(minutes=SESSION_TTL_MINUTES)
        row = mobile_upload_session_dao.create(
            db,
            obj_in={
                "workspace_id": workspace.id,
                "created_by": user.id,
                "entity_type": entity_type.value,
                "entity_id": entity_id,
                "entity_label": label,
                "token_hash": token_hash,
                "expires_at": expires_at,
                "status": MobileUploadSessionStatusEnum.WAITING.value,
                "delivery_type": AUTHENTICATED_DELIVERY_TYPE,
            },
        )
        db.flush()
        return row, raw_token

    def to_create_response(
        self,
        session: MobileUploadSession,
        raw_token: str,
    ) -> MobileUploadSessionCreateResponse:
        return MobileUploadSessionCreateResponse(
            session_id=session.id,
            token=raw_token,
            expires_at=session.expires_at,
            entity_label=session.entity_label,
        )

    def _ensure_active(self, session: MobileUploadSession) -> MobileUploadSession:
        if session.status in {
            MobileUploadSessionStatusEnum.CONSUMED.value,
            MobileUploadSessionStatusEnum.CANCELLED.value,
            MobileUploadSessionStatusEnum.EXPIRED.value,
        }:
            raise MobileUploadSessionNotFoundError("Upload session is no longer available.")
        if _naive_utc(session.expires_at) <= utcnow():
            session.status = MobileUploadSessionStatusEnum.EXPIRED.value
            raise MobileUploadSessionNotFoundError("Upload session has expired.")
        return session

    def get_by_raw_token(self, db: Session, *, raw_token: str) -> MobileUploadSession:
        token_hash = self._hash_token(raw_token)
        session = mobile_upload_session_dao.get_by_token_hash(db, token_hash=token_hash)
        if not session:
            raise MobileUploadSessionNotFoundError("Upload session not found.")
        return self._ensure_active(session)

    def get_for_creator(
        self,
        db: Session,
        *,
        session_id: int,
        workspace_id: int,
        user_id: int,
    ) -> MobileUploadSession:
        session = mobile_upload_session_dao.get_for_creator(
            db,
            session_id=session_id,
            workspace_id=workspace_id,
            created_by=user_id,
        )
        if not session:
            raise MobileUploadSessionNotFoundError("Upload session not found.")
        mobile_upload_session_dao.mark_expired_if_needed(session)
        if session.status == MobileUploadSessionStatusEnum.EXPIRED.value:
            raise MobileUploadSessionNotFoundError("Upload session has expired.")
        return session

    def _staging_preview_url(self, session: MobileUploadSession) -> str | None:
        if session.status != MobileUploadSessionStatusEnum.UPLOADED.value:
            return None
        if not session.public_id or not session.version or not session.format:
            return None
        mime = (session.mime_type or "").lower()
        if not mime.startswith("image/") or mime == "application/pdf":
            return None
        try:
            return build_signed_delivery_url(
                public_id=session.public_id,
                resource_type=session.resource_type or "image",
                delivery_type=session.delivery_type or AUTHENTICATED_DELIVERY_TYPE,
                version=int(session.version),
                fmt=session.format,
                transformation=[{"width": 400, "crop": "limit"}],
            )
        except Exception:
            return None

    def to_session_response(self, session: MobileUploadSession) -> MobileUploadSessionResponse:
        return MobileUploadSessionResponse(
            id=session.id,
            status=MobileUploadSessionStatusEnum(session.status),
            entity_type=AttachmentEntityTypeEnum(session.entity_type),
            entity_id=session.entity_id,
            entity_label=session.entity_label,
            expires_at=session.expires_at,
            file_name=session.file_name,
            mime_type=session.mime_type,
            file_size=session.file_size,
            preview_url=self._staging_preview_url(session),
        )

    def to_public_response(self, session: MobileUploadSession) -> MobileUploadPublicSessionResponse:
        return MobileUploadPublicSessionResponse(
            status=MobileUploadSessionStatusEnum(session.status),
            entity_label=session.entity_label,
            expires_at=session.expires_at,
        )

    def normalize_public_sign(
        self,
        *,
        file_name: str,
        mime_type: str,
        file_size: int,
    ):
        payload = AttachmentSignRequest(
            entity_type=AttachmentEntityTypeEnum.SCRATCH,
            entity_id=1,
            file_name=file_name,
            mime_type=mime_type,
            file_size=file_size,
        )
        return self.attachment_mgr.normalize_upload_request(payload)

    def sign_staging_upload(
        self,
        db: Session,
        *,
        session: MobileUploadSession,
        workspace: Workspace,
        file_name: str,
        mime_type: str,
        file_size: int,
    ) -> MobileUploadPublicSignResponse:
        if session.status != MobileUploadSessionStatusEnum.WAITING.value:
            raise MobileUploadSessionError("This session already received a file.")

        if session.public_id:
            self._destroy_staging_asset(session)
            session.public_id = None
            session.asset_folder = None

        normalized = self.normalize_public_sign(
            file_name=file_name,
            mime_type=mime_type,
            file_size=file_size,
        )
        public_id = self.build_staging_public_id(
            workspace_id=workspace.id,
            session_id=session.id,
        )
        asset_folder = self.build_staging_asset_folder(
            workspace_name=workspace.name,
            session_id=session.id,
        )
        display_name = self.attachment_mgr.build_display_name(normalized.file_name)

        session.public_id = public_id
        session.asset_folder = asset_folder
        session.resource_type = normalized.resource_type
        session.file_name = normalized.file_name
        session.mime_type = normalized.mime_type
        session.file_size = file_size
        db.add(session)
        db.flush()

        if not settings.CLOUDINARY_CLOUD_NAME or not settings.CLOUDINARY_API_KEY:
            raise CloudinaryNotConfiguredError("Cloudinary cloud name and API key are required.")

        timestamp = int(time.time())
        signature = generate_upload_signature(
            public_id=public_id,
            asset_folder=asset_folder,
            display_name=display_name,
            timestamp=timestamp,
            delivery_type=AUTHENTICATED_DELIVERY_TYPE,
        )
        resource_type = normalized.resource_type
        upload_url = f"https://api.cloudinary.com/v1_1/{settings.CLOUDINARY_CLOUD_NAME}/{resource_type}/upload"

        return MobileUploadPublicSignResponse(
            cloud_name=settings.CLOUDINARY_CLOUD_NAME,
            api_key=settings.CLOUDINARY_API_KEY,
            timestamp=timestamp,
            public_id=public_id,
            asset_folder=asset_folder,
            display_name=display_name,
            type=AUTHENTICATED_DELIVERY_TYPE,
            signature=signature,
            resource_type=resource_type,
            upload_url=upload_url,
        )

    def confirm_staging_upload(
        self,
        db: Session,
        *,
        session: MobileUploadSession,
    ) -> MobileUploadSession:
        if session.status != MobileUploadSessionStatusEnum.WAITING.value:
            raise MobileUploadSessionError("This session already received a file.")
        if not session.public_id or not session.file_name:
            raise MobileUploadSessionError("Upload was not prepared.")

        try:
            resource: dict[str, Any] = get_resource(
                public_id=session.public_id,
                resource_type=session.resource_type or "image",
                delivery_type=session.delivery_type or AUTHENTICATED_DELIVERY_TYPE,
            )
        except Exception as exc:
            raise AttachmentConfirmError(f"Cloudinary verification failed: {exc}") from exc

        validate_cloudinary_resource(file_name=session.file_name, resource=resource)

        bytes_count = int(resource.get("bytes") or 0)
        if bytes_count > MAX_FILE_SIZE_BYTES:
            self._destroy_staging_asset(session)
            session.public_id = None
            session.asset_folder = None
            db.add(session)
            db.flush()
            raise AttachmentConfirmError(
                f"File too large ({bytes_count} bytes). Maximum is {MAX_FILE_SIZE_BYTES} bytes."
            )

        session.format = resource.get("format")
        session.version = resource.get("version")
        session.file_size = resource.get("bytes") or session.file_size
        if resource.get("resource_type") == "image" and resource.get("format") == "pdf":
            session.mime_type = "application/pdf"
        session.status = MobileUploadSessionStatusEnum.UPLOADED.value
        db.add(session)
        db.flush()
        return session

    def _destroy_staging_asset(self, session: MobileUploadSession) -> None:
        if not session.public_id:
            return
        try:
            destroy_resource(
                public_id=session.public_id,
                resource_type=session.resource_type or "image",
                delivery_type=session.delivery_type or AUTHENTICATED_DELIVERY_TYPE,
            )
        except Exception:
            pass

    def cancel_session(self, db: Session, *, session: MobileUploadSession) -> MobileUploadSession:
        if session.status == MobileUploadSessionStatusEnum.CONSUMED.value:
            return session
        if session.status == MobileUploadSessionStatusEnum.UPLOADED.value:
            self._destroy_staging_asset(session)
        session.status = MobileUploadSessionStatusEnum.CANCELLED.value
        db.add(session)
        db.flush()
        return session

    def _promote_file_name(self, session: MobileUploadSession, requested: str | None) -> str:
        original = session.file_name or "upload.jpg"
        original_ext = original.rsplit(".", 1)[-1] if "." in original else "jpg"
        if not requested or not requested.strip():
            return original
        base = requested.strip()
        if "." in base:
            base = base.rsplit(".", 1)[0]
        return sanitize_file_name(f"{base}.{original_ext}")

    def promote_to_attachment(
        self,
        db: Session,
        *,
        session: MobileUploadSession,
        workspace: Workspace,
        user: Profile,
        file_name: str | None,
        note: str | None,
    ) -> Attachment:
        if session.status != MobileUploadSessionStatusEnum.UPLOADED.value:
            raise MobileUploadSessionError("No file is ready on this session.")
        if not session.public_id or not session.file_name or not session.mime_type:
            raise MobileUploadSessionError("Staging metadata is incomplete.")

        file_size = int(session.file_size or 0)
        if file_size > MAX_FILE_SIZE_BYTES:
            raise AttachmentValidationError(
                f"File too large ({file_size} bytes). Maximum is {MAX_FILE_SIZE_BYTES} bytes."
            )

        promoted_name = self._promote_file_name(session, file_name)
        payload = AttachmentSignRequest(
            entity_type=AttachmentEntityTypeEnum(session.entity_type),
            entity_id=session.entity_id,
            file_name=promoted_name,
            mime_type=session.mime_type,
            file_size=max(file_size, 1),
            note=note,
        )
        normalized = self.attachment_mgr.normalize_upload_request(payload)
        dest_public_id = self.attachment_mgr.build_public_id(workspace_id=workspace.id)
        entity_label = self.attachment_mgr.resolve_entity_label(
            db,
            workspace_id=workspace.id,
            entity_type=payload.entity_type,
            entity_id=payload.entity_id,
        )
        asset_folder = self.attachment_mgr.build_asset_folder(
            workspace_name=workspace.name,
            entity_type=payload.entity_type,
            entity_label=entity_label,
        )
        display_name = self.attachment_mgr.build_display_name(normalized.file_name)
        resource_type = session.resource_type or normalized.resource_type
        delivery_type = session.delivery_type or AUTHENTICATED_DELIVERY_TYPE

        try:
            rename_resource(
                from_public_id=session.public_id,
                to_public_id=dest_public_id,
                resource_type=resource_type,
                delivery_type=delivery_type,
            )
        except Exception as exc:
            raise AttachmentConfirmError(f"Cloudinary move failed: {exc}") from exc

        session.public_id = dest_public_id
        session.asset_folder = asset_folder
        db.add(session)
        db.flush()

        try:
            update_resource_metadata(
                public_id=dest_public_id,
                resource_type=resource_type,
                delivery_type=delivery_type,
                asset_folder=asset_folder,
                display_name=display_name,
            )
        except Exception:
            pass

        attachment = self.attachment_mgr.create_pending_attachment(
            db,
            workspace_id=workspace.id,
            user=user,
            payload=payload,
            normalized=normalized,
            stored_public_id=dest_public_id,
            asset_folder=asset_folder,
        )
        attachment = self.attachment_mgr.confirm_attachment(
            db,
            attachment_id=attachment.id,
            workspace_id=workspace.id,
            performed_by=user.id,
        )

        session.status = MobileUploadSessionStatusEnum.CONSUMED.value
        session.public_id = None
        db.add(session)
        db.flush()
        return attachment


mobile_upload_session_manager = MobileUploadSessionManager()
