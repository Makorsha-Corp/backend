"""Mobile upload session manager tests."""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.core.security import hash_refresh_token
from app.managers.mobile_upload_session_manager import (
    MobileUploadSessionError,
    MobileUploadSessionManager,
    MobileUploadSessionNotFoundError,
)
from app.models.enums import AttachmentEntityTypeEnum, MobileUploadSessionStatusEnum
from app.models.mobile_upload_session import MobileUploadSession
from app.utils.time import utcnow


def _session(**overrides) -> MobileUploadSession:
    row = MobileUploadSession(
        id=1,
        workspace_id=10,
        created_by=5,
        entity_type=AttachmentEntityTypeEnum.PURCHASE_ORDER.value,
        entity_id=42,
        entity_label="PO-2026-001",
        token_hash=hash_refresh_token("test-token"),
        expires_at=utcnow() + timedelta(minutes=10),
        status=MobileUploadSessionStatusEnum.WAITING.value,
        delivery_type="authenticated",
    )
    for key, value in overrides.items():
        setattr(row, key, value)
    return row


def test_create_session_token_unique_hash() -> None:
    manager = MobileUploadSessionManager()
    raw1, hash1 = manager.create_session_token()
    raw2, hash2 = manager.create_session_token()
    assert raw1 != raw2
    assert hash1 != hash2
    assert hash1 == hash_refresh_token(raw1)


@patch("app.managers.mobile_upload_session_manager.mobile_upload_session_dao")
def test_get_by_raw_token_not_found(mock_dao: MagicMock) -> None:
    mock_dao.get_by_token_hash.return_value = None
    manager = MobileUploadSessionManager()
    with pytest.raises(MobileUploadSessionNotFoundError):
        manager.get_by_raw_token(MagicMock(), raw_token="missing")


@patch("app.managers.mobile_upload_session_manager.mobile_upload_session_dao")
def test_get_by_raw_token_expired(mock_dao: MagicMock) -> None:
    from datetime import timezone

    session = _session(expires_at=datetime.now(timezone.utc) - timedelta(minutes=1))
    mock_dao.get_by_token_hash.return_value = session
    manager = MobileUploadSessionManager()
    with pytest.raises(MobileUploadSessionNotFoundError, match="expired"):
        manager.get_by_raw_token(MagicMock(), raw_token="test-token")
    assert session.status == MobileUploadSessionStatusEnum.EXPIRED.value


@patch("app.managers.mobile_upload_session_manager.mobile_upload_session_dao")
def test_get_by_raw_token_consumed(mock_dao: MagicMock) -> None:
    session = _session(status=MobileUploadSessionStatusEnum.CONSUMED.value)
    mock_dao.get_by_token_hash.return_value = session
    manager = MobileUploadSessionManager()
    with pytest.raises(MobileUploadSessionNotFoundError):
        manager.get_by_raw_token(MagicMock(), raw_token="test-token")


@patch("app.managers.mobile_upload_session_manager.settings")
def test_build_staging_public_id_dev_prefix(mock_settings: MagicMock) -> None:
    mock_settings.CLOUDINARY_UPLOAD_ENV = "development"
    mock_settings.ENVIRONMENT = "development"
    manager = MobileUploadSessionManager()
    public_id = manager.build_staging_public_id(workspace_id=3, session_id=99)
    assert public_id.startswith("development/ws-3/mobile-staging/99/")


@patch("app.managers.mobile_upload_session_manager.destroy_resource")
def test_cancel_waiting_session(mock_destroy: MagicMock) -> None:
    session = _session(status=MobileUploadSessionStatusEnum.WAITING.value, public_id=None)
    db = MagicMock()
    manager = MobileUploadSessionManager()
    result = manager.cancel_session(db, session=session)
    assert result.status == MobileUploadSessionStatusEnum.CANCELLED.value
    mock_destroy.assert_not_called()


@patch("app.managers.mobile_upload_session_manager.destroy_resource")
@patch("app.managers.mobile_upload_session_manager.rename_resource")
@patch("app.managers.mobile_upload_session_manager.update_resource_metadata")
def test_promote_to_attachment(
    mock_update: MagicMock,
    mock_rename: MagicMock,
    mock_destroy: MagicMock,
) -> None:
    session = _session(
        status=MobileUploadSessionStatusEnum.UPLOADED.value,
        public_id="dev/ws-10/mobile-staging/1/abc",
        resource_type="image",
        format="jpg",
        version=123,
        file_name="scan.jpg",
        mime_type="image/jpeg",
        file_size=2048,
    )
    workspace = MagicMock()
    workspace.id = 10
    workspace.name = "Acme"
    user = MagicMock()
    user.id = 5
    db = MagicMock()
    attachment = MagicMock()
    attachment.id = 77

    manager = MobileUploadSessionManager()
    manager.attachment_mgr = MagicMock()
    manager.attachment_mgr.normalize_upload_request.return_value = MagicMock(
        file_name="receipt.jpg",
        mime_type="image/jpeg",
        resource_type="image",
    )
    manager.attachment_mgr.build_public_id.return_value = "development/ws-10/dest"
    manager.attachment_mgr.resolve_entity_label.return_value = "PO-1"
    manager.attachment_mgr.build_asset_folder.return_value = "Dev/Acme/Purchase Orders/PO-1"
    manager.attachment_mgr.build_display_name.return_value = "receipt.jpg"
    manager.attachment_mgr.create_pending_attachment.return_value = attachment
    manager.attachment_mgr.confirm_attachment.return_value = attachment

    result = manager.promote_to_attachment(
        db,
        session=session,
        workspace=workspace,
        user=user,
        file_name="receipt.jpg",
        note="from phone",
    )

    assert result is attachment
    assert session.status == MobileUploadSessionStatusEnum.CONSUMED.value
    assert session.public_id is None
    mock_rename.assert_called_once()
    mock_destroy.assert_not_called()
    mock_update.assert_called_once()


def test_promote_to_attachment_requires_uploaded() -> None:
    session = _session(status=MobileUploadSessionStatusEnum.WAITING.value)
    manager = MobileUploadSessionManager()
    with pytest.raises(MobileUploadSessionError, match="No file is ready"):
        manager.promote_to_attachment(
            MagicMock(),
            session=session,
            workspace=MagicMock(id=1, name="Acme"),
            user=MagicMock(id=5),
            file_name=None,
            note=None,
        )


@patch("app.managers.mobile_upload_session_manager.destroy_resource")
@patch("app.managers.mobile_upload_session_manager.generate_upload_signature")
@patch("app.managers.mobile_upload_session_manager.settings")
def test_sign_staging_upload_destroys_previous_public_id(
    mock_settings: MagicMock,
    mock_sign: MagicMock,
    mock_destroy: MagicMock,
) -> None:
    mock_settings.CLOUDINARY_CLOUD_NAME = "demo"
    mock_settings.CLOUDINARY_API_KEY = "key"
    mock_settings.CLOUDINARY_UPLOAD_ENV = "development"
    mock_sign.return_value = "sig"
    workspace = MagicMock()
    workspace.id = 10
    workspace.name = "Acme"
    session = _session(
        public_id="old-staging-id",
        resource_type="image",
        asset_folder="old-folder",
    )
    manager = MobileUploadSessionManager()
    manager.sign_staging_upload(
        MagicMock(),
        session=session,
        workspace=workspace,
        file_name="photo.jpg",
        mime_type="image/jpeg",
        file_size=2048,
    )
    mock_destroy.assert_called_once()
    assert session.public_id != "old-staging-id"


@patch("app.managers.mobile_upload_session_manager.destroy_resource")
@patch("app.managers.mobile_upload_session_manager.get_resource")
def test_confirm_staging_rejects_oversized(
    mock_get: MagicMock,
    mock_destroy: MagicMock,
) -> None:
    from app.utils.attachment_allowlist import AttachmentConfirmError, MAX_FILE_SIZE_BYTES

    session = _session(
        public_id="staging-id",
        file_name="photo.jpg",
        mime_type="image/jpeg",
        resource_type="image",
    )
    mock_get.return_value = {
        "bytes": MAX_FILE_SIZE_BYTES + 1,
        "format": "jpg",
        "resource_type": "image",
        "version": 1,
    }
    manager = MobileUploadSessionManager()
    with pytest.raises(AttachmentConfirmError, match="too large"):
        manager.confirm_staging_upload(MagicMock(), session=session)
    mock_destroy.assert_called_once()
    assert session.public_id is None
    assert session.status == MobileUploadSessionStatusEnum.WAITING.value


@patch("app.managers.mobile_upload_session_manager.settings")
@patch("app.managers.mobile_upload_session_manager.generate_upload_signature")
def test_sign_staging_upload_sets_metadata(
    mock_sign: MagicMock,
    mock_settings: MagicMock,
) -> None:
    mock_settings.CLOUDINARY_CLOUD_NAME = "demo"
    mock_settings.CLOUDINARY_API_KEY = "key"
    mock_settings.CLOUDINARY_UPLOAD_ENV = "development"
    mock_sign.return_value = "sig"
    workspace = MagicMock()
    workspace.id = 10
    workspace.name = "Acme"
    session = _session()
    db = MagicMock()
    manager = MobileUploadSessionManager()

    response = manager.sign_staging_upload(
        db,
        session=session,
        workspace=workspace,
        file_name="photo.jpg",
        mime_type="image/jpeg",
        file_size=2048,
    )

    assert response.signature == "sig"
    assert session.public_id is not None
    assert session.file_name == "photo.jpg"
    assert session.mime_type == "image/jpeg"
    assert session.file_size == 2048


def test_sign_staging_upload_rejects_non_waiting() -> None:
    session = _session(status=MobileUploadSessionStatusEnum.UPLOADED.value)
    manager = MobileUploadSessionManager()
    with pytest.raises(MobileUploadSessionError, match="already received"):
        manager.sign_staging_upload(
            MagicMock(),
            session=session,
            workspace=MagicMock(id=1, name="Acme"),
            file_name="photo.jpg",
            mime_type="image/jpeg",
            file_size=2048,
        )


def test_mark_expired_if_needed_accepts_aware_datetime() -> None:
    from app.dao.mobile_upload_session import mobile_upload_session_dao

    session = _session(expires_at=datetime.now(timezone.utc) + timedelta(minutes=5))
    result = mobile_upload_session_dao.mark_expired_if_needed(session)
    assert result.status == MobileUploadSessionStatusEnum.WAITING.value
