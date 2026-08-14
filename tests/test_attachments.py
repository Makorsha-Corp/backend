"""Attachment manager and Cloudinary upload tests."""
from unittest.mock import MagicMock, patch

import pytest

from app.managers.attachment_manager import (
    ALLOWED_MIME_TYPES,
    MAX_FILE_SIZE_BYTES,
    AttachmentConfirmError,
    AttachmentManager,
    AttachmentValidationError,
)
from app.models.enums import AttachmentEntityTypeEnum
from app.schemas.attachment import AttachmentSignRequest


def _sign_payload(**overrides) -> AttachmentSignRequest:
    data = {
        "entity_type": AttachmentEntityTypeEnum.SCRATCH,
        "entity_id": 1,
        "file_name": "invoice.pdf",
        "mime_type": "application/pdf",
        "file_size": 1024,
    }
    data.update(overrides)
    return AttachmentSignRequest(**data)


MIME_BY_EXT = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
    "heic": "image/heic",
    "heif": "image/heif",
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "txt": "text/plain",
    "csv": "text/csv",
}


def test_validate_rejects_disallowed_extension() -> None:
    manager = AttachmentManager()
    with pytest.raises(AttachmentValidationError, match="Unsupported file extension"):
        manager.normalize_upload_request(_sign_payload(file_name="archive.zip", mime_type="application/zip"))


def test_validate_rejects_disallowed_mime_for_extension() -> None:
    manager = AttachmentManager()
    with pytest.raises(AttachmentValidationError, match="does not match"):
        manager.normalize_upload_request(
            _sign_payload(file_name="photo.png", mime_type="application/pdf")
        )


def test_validate_rejects_extension_mismatch_bin() -> None:
    manager = AttachmentManager()
    with pytest.raises(AttachmentValidationError, match="Unsupported file extension"):
        manager.normalize_upload_request(_sign_payload(file_name="x.bin", mime_type="image/png"))


def test_validate_rejects_macro_office_types() -> None:
    manager = AttachmentManager()
    for file_name, mime_type in (
        ("legacy.doc", "application/msword"),
        ("legacy.xls", "application/vnd.ms-excel"),
        ("macro.docm", "application/vnd.ms-word.document.macroEnabled.12"),
        ("macro.xlsm", "application/vnd.ms-excel.sheet.macroEnabled.12"),
    ):
        with pytest.raises(AttachmentValidationError):
            manager.normalize_upload_request(
                _sign_payload(file_name=file_name, mime_type=mime_type)
            )


def test_validate_rejects_script_types() -> None:
    manager = AttachmentManager()
    for file_name, mime_type in (
        ("page.svg", "image/svg+xml"),
        ("page.html", "text/html"),
        ("app.js", "application/javascript"),
        ("setup.exe", "application/octet-stream"),
    ):
        with pytest.raises(AttachmentValidationError):
            manager.normalize_upload_request(
                _sign_payload(file_name=file_name, mime_type=mime_type)
            )


def test_validate_rejects_oversized_file() -> None:
    manager = AttachmentManager()
    with pytest.raises(AttachmentValidationError, match="File too large"):
        manager.normalize_upload_request(
            _sign_payload(file_size=MAX_FILE_SIZE_BYTES + 1)
        )


@pytest.mark.parametrize(
    "ext",
    ["jpg", "jpeg", "png", "webp", "heic", "heif", "pdf", "docx", "xlsx", "txt", "csv"],
)
def test_validate_accepts_allowed_types(ext: str) -> None:
    manager = AttachmentManager()
    normalized = manager.normalize_upload_request(
        _sign_payload(file_name=f"sample.{ext}", mime_type=MIME_BY_EXT[ext])
    )
    assert normalized.extension == ext if ext != "jpeg" else normalized.extension in {"jpg", "jpeg"}
    assert normalized.file_name == f"sample.{ext}"


def test_validate_sanitizes_file_name() -> None:
    manager = AttachmentManager()
    normalized = manager.normalize_upload_request(
        _sign_payload(file_name='bad/name<script>.pdf', mime_type="application/pdf")
    )
    assert "/" not in normalized.file_name
    assert "<" not in normalized.file_name
    assert normalized.file_name.endswith(".pdf")


def test_normalize_sets_resource_type_for_raw() -> None:
    manager = AttachmentManager()
    normalized = manager.normalize_upload_request(
        _sign_payload(
            file_name="notes.txt",
            mime_type="text/plain",
        )
    )
    assert normalized.resource_type == "raw"


@patch("app.managers.attachment_manager.settings")
def test_build_public_id_non_production(mock_settings: MagicMock) -> None:
    mock_settings.CLOUDINARY_UPLOAD_ENV = "development"
    mock_settings.ENVIRONMENT = "development"

    manager = AttachmentManager()
    public_id = manager.build_public_id(workspace_id=1)

    assert public_id.startswith("development/ws-1/")
    assert len(public_id.split("/")[-1]) == 32


@patch("app.managers.attachment_manager.settings")
def test_build_public_id_production(mock_settings: MagicMock) -> None:
    mock_settings.CLOUDINARY_UPLOAD_ENV = "production"
    mock_settings.ENVIRONMENT = "production"

    manager = AttachmentManager()
    public_id = manager.build_public_id(workspace_id=3)

    assert public_id.startswith("ws-3/")
    assert "development" not in public_id


@patch("app.managers.attachment_manager.settings")
def test_build_asset_folder_non_production(mock_settings: MagicMock) -> None:
    mock_settings.CLOUDINARY_UPLOAD_ENV = "development"

    manager = AttachmentManager()
    folder = manager.build_asset_folder(
        workspace_name="Akbar Cotton Mill",
        entity_type=AttachmentEntityTypeEnum.PURCHASE_ORDER,
        entity_label="PO-2026-001",
    )

    assert folder == "Dev/Akbar Cotton Mill/Purchase Orders/PO-2026-001"


@patch("app.managers.attachment_manager.settings")
def test_build_asset_folder_production(mock_settings: MagicMock) -> None:
    mock_settings.CLOUDINARY_UPLOAD_ENV = "production"

    manager = AttachmentManager()
    folder = manager.build_asset_folder(
        workspace_name="Akbar Cotton Mill",
        entity_type=AttachmentEntityTypeEnum.SALES_ORDER,
        entity_label="SO-2026-001",
    )

    assert folder == "Akbar Cotton Mill/Sales Orders/SO-2026-001"


def test_build_display_name_strips_slashes() -> None:
    manager = AttachmentManager()
    assert manager.build_display_name("invoices/scan.png") == "invoices-scan.png"


@patch("app.managers.attachment_manager.purchase_order_dao")
def test_resolve_entity_label_purchase_order(mock_po_dao: MagicMock) -> None:
    row = MagicMock()
    row.po_number = "PO-2026-001"
    mock_po_dao.get_by_id_and_workspace.return_value = row

    manager = AttachmentManager()
    label = manager.resolve_entity_label(
        MagicMock(),
        workspace_id=1,
        entity_type=AttachmentEntityTypeEnum.PURCHASE_ORDER,
        entity_id=42,
    )

    assert label == "PO-2026-001"
    mock_po_dao.get_by_id_and_workspace.assert_called_once()


@patch("app.managers.attachment_manager.purchase_order_dao")
def test_resolve_entity_label_fallback_when_missing(mock_po_dao: MagicMock) -> None:
    mock_po_dao.get_by_id_and_workspace.return_value = None

    manager = AttachmentManager()
    label = manager.resolve_entity_label(
        MagicMock(),
        workspace_id=1,
        entity_type=AttachmentEntityTypeEnum.PURCHASE_ORDER,
        entity_id=42,
    )

    assert label == "purchase_order-42"


@patch("app.managers.attachment_manager.settings")
@patch("app.managers.attachment_manager.generate_upload_signature")
def test_build_sign_response_image(mock_sign: MagicMock, mock_settings: MagicMock) -> None:
    mock_settings.CLOUDINARY_CLOUD_NAME = "demo"
    mock_settings.CLOUDINARY_API_KEY = "123456"
    mock_sign.return_value = "abc123sig"

    attachment = MagicMock()
    attachment.id = 42
    attachment.resource_type = "image"

    manager = AttachmentManager()
    response = manager.build_sign_response(
        attachment=attachment,
        public_id="development/ws-1/deadbeef",
        asset_folder="Dev/Akbar Cotton Mill/Scratch/scratch-1",
        display_name="invoice.pdf",
    )

    assert response.upload_url == "https://api.cloudinary.com/v1_1/demo/image/upload"
    assert response.resource_type == "image"


@patch("app.managers.attachment_manager.settings")
@patch("app.managers.attachment_manager.generate_upload_signature")
def test_build_sign_response_raw(mock_sign: MagicMock, mock_settings: MagicMock) -> None:
    mock_settings.CLOUDINARY_CLOUD_NAME = "demo"
    mock_settings.CLOUDINARY_API_KEY = "123456"
    mock_sign.return_value = "abc123sig"

    attachment = MagicMock()
    attachment.id = 43
    attachment.resource_type = "raw"

    manager = AttachmentManager()
    response = manager.build_sign_response(
        attachment=attachment,
        public_id="development/ws-1/deadbeef",
        asset_folder="Dev/Akbar Cotton Mill/Scratch/scratch-1",
        display_name="notes.txt",
    )

    assert response.upload_url == "https://api.cloudinary.com/v1_1/demo/raw/upload"
    assert response.resource_type == "raw"


@patch("app.managers.attachment_manager.settings")
@patch("app.managers.attachment_manager.build_signed_delivery_url")
def test_build_pdf_page_image_url(mock_build_url: MagicMock, mock_settings: MagicMock) -> None:
    mock_settings.CLOUDINARY_CLOUD_NAME = "demo"
    mock_settings.CLOUDINARY_API_SECRET = "secret"
    mock_build_url.return_value = "https://res.cloudinary.com/demo/page-2.jpg"

    attachment = MagicMock()
    attachment.upload_status = "ready"
    attachment.mime_type = "application/pdf"
    attachment.format = "pdf"
    attachment.public_id = "development/ws-1/abc"
    attachment.version = 1710000000
    attachment.resource_type = "image"
    attachment.delivery_type = "authenticated"
    attachment.page_count = 5

    manager = AttachmentManager()
    url = manager.build_pdf_page_image_url(attachment, page=2)

    assert url == "https://res.cloudinary.com/demo/page-2.jpg"
    mock_build_url.assert_called_once()
    assert mock_build_url.call_args.kwargs["fmt"] == "jpg"
    assert mock_build_url.call_args.kwargs["transformation"][0]["page"] == 2


@patch("app.managers.attachment_manager.attachment_link_dao")
@patch("app.managers.attachment_manager.attachment_dao")
def test_create_pending_attachment_passes_resource_type(
    mock_attachment_dao: MagicMock,
    mock_link_dao: MagicMock,
) -> None:
    created = MagicMock()
    created.id = 99
    mock_attachment_dao.create.return_value = created

    session = MagicMock()
    user = MagicMock()
    user.id = 5
    payload = _sign_payload(file_name="notes.txt", mime_type="text/plain")
    normalized = AttachmentManager().normalize_upload_request(payload)

    manager = AttachmentManager()
    result = manager.create_pending_attachment(
        session,
        workspace_id=2,
        user=user,
        payload=payload,
        normalized=normalized,
        stored_public_id="development/ws-2/abc",
        asset_folder="Dev/Test Workspace/Scratch/scratch-1",
    )

    assert result is created
    create_payload = mock_attachment_dao.create.call_args.kwargs["obj_in"]
    assert create_payload["public_id"] == "development/ws-2/abc"
    assert create_payload["resource_type"] == "raw"
    assert create_payload["file_name"] == "notes.txt"
    mock_link_dao.create.assert_called_once()


@patch("app.managers.attachment_manager.get_resource")
@patch("app.managers.attachment_manager.attachment_dao")
def test_confirm_attachment_updates_from_cloudinary(
    mock_dao: MagicMock,
    mock_get_resource: MagicMock,
) -> None:
    attachment = MagicMock()
    attachment.id = 7
    attachment.public_id = "development/ws-1/abc"
    attachment.resource_type = "image"
    attachment.delivery_type = "authenticated"
    attachment.upload_status = "pending"
    attachment.file_size = 100
    attachment.mime_type = "application/pdf"
    attachment.file_name = "invoice.pdf"

    mock_dao.get_active.return_value = attachment
    mock_get_resource.return_value = {
        "secure_url": "https://res.cloudinary.com/demo/image/upload/v1/x.pdf",
        "bytes": 2048,
        "format": "pdf",
        "version": 1710000000,
        "width": 800,
        "height": 1100,
        "pages": 12,
        "asset_id": "asset-1",
        "etag": "etag-1",
        "resource_type": "image",
    }

    session = MagicMock()
    manager = AttachmentManager()
    result = manager.confirm_attachment(
        session, attachment_id=7, workspace_id=1, performed_by=5
    )

    mock_get_resource.assert_called_once_with(
        public_id="development/ws-1/abc",
        resource_type="image",
        delivery_type="authenticated",
    )
    mock_dao.update.assert_called_once()
    update_payload = mock_dao.update.call_args.kwargs["obj_in"]
    assert update_payload["upload_status"] == "ready"
    assert update_payload["format"] == "pdf"
    assert update_payload["page_count"] == 12
    assert result is attachment


@patch("app.managers.attachment_manager.get_resource")
@patch("app.managers.attachment_manager.attachment_dao")
def test_confirm_attachment_rejects_format_mismatch(
    mock_dao: MagicMock,
    mock_get_resource: MagicMock,
) -> None:
    attachment = MagicMock()
    attachment.id = 8
    attachment.public_id = "development/ws-1/abc"
    attachment.resource_type = "raw"
    attachment.delivery_type = "authenticated"
    attachment.upload_status = "pending"
    attachment.file_size = 100
    attachment.mime_type = "text/plain"
    attachment.file_name = "notes.txt"

    mock_dao.get_active.return_value = attachment
    mock_get_resource.return_value = {
        "secure_url": "https://res.cloudinary.com/demo/raw/upload/v1/x.exe",
        "bytes": 2048,
        "format": "exe",
        "version": 1710000000,
        "resource_type": "raw",
    }

    session = MagicMock()
    manager = AttachmentManager()
    with pytest.raises(AttachmentConfirmError, match="format"):
        manager.confirm_attachment(session, attachment_id=8, workspace_id=1)

    assert attachment.upload_status == "failed"
    mock_dao.update.assert_not_called()


@patch.object(AttachmentManager, "_log_attachment_entity_events")
@patch("app.managers.attachment_manager.get_resource")
@patch("app.managers.attachment_manager.attachment_dao")
def test_confirm_attachment_logs_entity_event(
    mock_dao: MagicMock,
    mock_get_resource: MagicMock,
    mock_log_events: MagicMock,
) -> None:
    attachment = MagicMock()
    attachment.id = 7
    attachment.public_id = "development/ws-1/abc"
    attachment.resource_type = "image"
    attachment.delivery_type = "authenticated"
    attachment.upload_status = "pending"
    attachment.file_size = 100
    attachment.mime_type = "application/pdf"
    attachment.file_name = "invoice.pdf"

    mock_dao.get_active.return_value = attachment
    mock_get_resource.return_value = {
        "secure_url": "https://res.cloudinary.com/demo/image/upload/v1/x.pdf",
        "bytes": 2048,
        "format": "pdf",
        "version": 1710000000,
        "width": 800,
        "height": 1100,
        "pages": 12,
        "asset_id": "asset-1",
        "etag": "etag-1",
        "resource_type": "image",
    }

    session = MagicMock()
    manager = AttachmentManager()
    manager.confirm_attachment(session, attachment_id=7, workspace_id=1, performed_by=99)

    mock_log_events.assert_called_once()


@patch.object(AttachmentManager, "_log_attachment_entity_events")
@patch("app.managers.attachment_manager.attachment_dao")
def test_confirm_attachment_skips_event_when_already_ready(
    mock_dao: MagicMock,
    mock_log_events: MagicMock,
) -> None:
    attachment = MagicMock()
    attachment.id = 7
    attachment.upload_status = "ready"

    mock_dao.get_active.return_value = attachment

    session = MagicMock()
    manager = AttachmentManager()
    manager.confirm_attachment(session, attachment_id=7, workspace_id=1, performed_by=99)

    mock_log_events.assert_not_called()


@patch("app.managers.attachment_manager.destroy_resource")
@patch.object(AttachmentManager, "_log_attachment_entity_events")
@patch("app.managers.attachment_manager.attachment_dao")
def test_delete_attachment_logs_entity_event(
    mock_dao: MagicMock,
    mock_log_events: MagicMock,
    mock_destroy: MagicMock,
) -> None:
    attachment = MagicMock()
    attachment.id = 7
    attachment.public_id = "development/ws-1/abc"
    attachment.resource_type = "image"
    attachment.delivery_type = "authenticated"
    attachment.upload_status = "ready"
    attachment.file_name = "scan.png"

    mock_dao.soft_delete.return_value = attachment

    session = MagicMock()
    manager = AttachmentManager()
    manager.delete_attachment(session, attachment_id=7, workspace_id=1, deleted_by=42)

    mock_log_events.assert_called_once()
    mock_destroy.assert_called_once()


def test_derive_urls_authenticated_includes_signature() -> None:
    attachment = MagicMock()
    attachment.upload_status = "ready"
    attachment.public_id = "development/ws-1/abc123"
    attachment.version = 1786367036
    attachment.format = "png"
    attachment.resource_type = "image"
    attachment.delivery_type = "authenticated"
    attachment.mime_type = "image/png"

    with patch("app.managers.attachment_manager.settings") as mock_settings:
        mock_settings.CLOUDINARY_CLOUD_NAME = "demo"
        mock_settings.CLOUDINARY_API_KEY = "123"
        mock_settings.CLOUDINARY_API_SECRET = "secret"
        manager = AttachmentManager()
        urls = manager.derive_urls(attachment)

    assert urls.thumb_url is not None
    assert "/image/authenticated/s--" in urls.thumb_url
    assert urls.preview_url is not None
    assert urls.download_url is not None


def test_derive_urls_raw_download_only() -> None:
    attachment = MagicMock()
    attachment.upload_status = "ready"
    attachment.public_id = "development/ws-1/abc123"
    attachment.version = 1786367036
    attachment.format = "docx"
    attachment.resource_type = "raw"
    attachment.delivery_type = "authenticated"
    attachment.mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    with patch("app.managers.attachment_manager.settings") as mock_settings:
        mock_settings.CLOUDINARY_CLOUD_NAME = "demo"
        mock_settings.CLOUDINARY_API_KEY = "123"
        mock_settings.CLOUDINARY_API_SECRET = "secret"
        manager = AttachmentManager()
        urls = manager.derive_urls(attachment)

    assert urls.thumb_url is None
    assert urls.preview_url is None
    assert urls.download_url is not None
    assert "/raw/authenticated/s--" in urls.download_url


def test_allowed_mime_types_cover_all_specs() -> None:
    for ext, mime in MIME_BY_EXT.items():
        assert mime in ALLOWED_MIME_TYPES, f"{mime} for .{ext} missing from allowlist"


def test_attachment_routes_registered() -> None:
    from app.main import app

    paths = app.openapi()["paths"]
    assert "/api/v1/attachments/sign" in paths
    assert "post" in paths["/api/v1/attachments/sign"]
    assert "/api/v1/attachments/" in paths
    assert "get" in paths["/api/v1/attachments/"]
    assert "/api/v1/attachments/{attachment_id}/pdf-page" in paths
