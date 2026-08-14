"""Attachment ledger tests."""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.dao.attachment_ledger import attachment_ledger_dao
from app.managers.attachment_manager import AttachmentConfirmError, AttachmentManager
from app.models.attachment import Attachment
from app.models.attachment_ledger import AttachmentLedger
from app.models.enums import AttachmentEntityTypeEnum, AttachmentLedgerTransactionTypeEnum, UploadStatusEnum
from app.schemas.attachment import AttachmentSignRequest
from app.utils.attachment_allowlist import NormalizedUploadRequest


def _attachment(**overrides) -> Attachment:
    row = Attachment(
        id=42,
        workspace_id=10,
        file_name="scan.jpg",
        mime_type="image/jpeg",
        file_size=2048,
        uploaded_by=5,
        upload_status=UploadStatusEnum.PENDING.value,
        public_id="dev/ws-10/abc",
        resource_type="image",
        delivery_type="authenticated",
    )
    for key, value in overrides.items():
        setattr(row, key, value)
    return row


def _normalized() -> NormalizedUploadRequest:
    return NormalizedUploadRequest(
        file_name="scan.jpg",
        mime_type="image/jpeg",
        resource_type="image",
        extension="jpg",
        spec=MagicMock(),
    )


@patch("app.managers.attachment_manager.attachment_ledger_dao")
@patch("app.managers.attachment_manager.attachment_link_dao")
@patch("app.managers.attachment_manager.attachment_dao")
def test_create_pending_appends_ledger(
    mock_attachment_dao: MagicMock,
    mock_link_dao: MagicMock,
    mock_ledger_dao: MagicMock,
) -> None:
    attachment = _attachment()
    mock_attachment_dao.create.return_value = attachment
    user = MagicMock()
    user.id = 5
    payload = AttachmentSignRequest(
        entity_type=AttachmentEntityTypeEnum.PURCHASE_ORDER,
        entity_id=99,
        file_name="scan.jpg",
        mime_type="image/jpeg",
        file_size=2048,
    )
    manager = AttachmentManager()
    db = MagicMock()

    result = manager.create_pending_attachment(
        db,
        workspace_id=10,
        user=user,
        payload=payload,
        normalized=_normalized(),
        stored_public_id="dev/ws-10/abc",
        asset_folder="Dev/Acme/Purchase Orders/PO-1",
    )

    assert result is attachment
    mock_ledger_dao.create.assert_called_once()
    ledger_payload = mock_ledger_dao.create.call_args.kwargs["obj_in"]
    assert ledger_payload["transaction_type"] == AttachmentLedgerTransactionTypeEnum.PENDING.value
    assert ledger_payload["entity_type"] == AttachmentEntityTypeEnum.PURCHASE_ORDER.value
    assert ledger_payload["entity_id"] == 99
    assert ledger_payload["attachment_id"] == 42


@patch("app.managers.attachment_manager.attachment_ledger_dao")
@patch("app.managers.attachment_manager.attachment_dao")
@patch("app.managers.attachment_manager.get_resource")
@patch("app.managers.attachment_manager.validate_cloudinary_resource")
def test_confirm_success_appends_ready_ledger(
    mock_validate: MagicMock,
    mock_get_resource: MagicMock,
    mock_attachment_dao: MagicMock,
    mock_ledger_dao: MagicMock,
) -> None:
    attachment = _attachment(upload_status=UploadStatusEnum.PENDING.value)
    mock_attachment_dao.get_active.return_value = attachment
    mock_get_resource.return_value = {
        "secure_url": "https://cdn.example/scan.jpg",
        "bytes": 2048,
        "format": "jpg",
        "version": 1,
        "resource_type": "image",
    }
    mock_attachment_dao.update.return_value = attachment
    manager = AttachmentManager()
    db = MagicMock()
    db.refresh = MagicMock()

    with patch.object(manager, "_log_attachment_entity_events") as mock_entity_log:
        manager.confirm_attachment(
            db,
            attachment_id=42,
            workspace_id=10,
            performed_by=5,
        )

    mock_ledger_dao.create.assert_called_once()
    assert mock_ledger_dao.create.call_args.kwargs["obj_in"]["transaction_type"] == "ready"
    mock_entity_log.assert_called_once()


@patch("app.managers.attachment_manager.attachment_ledger_dao")
@patch("app.managers.attachment_manager.attachment_dao")
@patch("app.managers.attachment_manager.get_resource")
def test_confirm_cloudinary_failure_appends_failed_ledger(
    mock_get_resource: MagicMock,
    mock_attachment_dao: MagicMock,
    mock_ledger_dao: MagicMock,
) -> None:
    attachment = _attachment(upload_status=UploadStatusEnum.PENDING.value)
    mock_attachment_dao.get_active.return_value = attachment
    mock_get_resource.side_effect = RuntimeError("missing asset")
    manager = AttachmentManager()
    db = MagicMock()

    with pytest.raises(AttachmentConfirmError):
        manager.confirm_attachment(db, attachment_id=42, workspace_id=10, performed_by=5)

    mock_ledger_dao.create.assert_called_once()
    assert mock_ledger_dao.create.call_args.kwargs["obj_in"]["transaction_type"] == "failed"


@patch("app.managers.attachment_manager.attachment_ledger_dao")
@patch("app.managers.attachment_manager.attachment_dao")
@patch("app.managers.attachment_manager.destroy_resource")
def test_delete_appends_deleted_ledger(
    mock_destroy: MagicMock,
    mock_attachment_dao: MagicMock,
    mock_ledger_dao: MagicMock,
) -> None:
    attachment = _attachment(upload_status=UploadStatusEnum.READY.value)
    mock_attachment_dao.soft_delete.return_value = attachment
    manager = AttachmentManager()
    db = MagicMock()

    with patch.object(manager, "_log_attachment_entity_events") as mock_entity_log:
        manager.delete_attachment(db, attachment_id=42, workspace_id=10, deleted_by=5)

    mock_ledger_dao.create.assert_called_once()
    assert mock_ledger_dao.create.call_args.kwargs["obj_in"]["transaction_type"] == "deleted"
    mock_entity_log.assert_called_once()
    mock_destroy.assert_called_once()


def test_dao_get_by_workspace_filters_workspace() -> None:
    db = MagicMock()
    query = db.query.return_value
    query.filter.return_value = query
    query.order_by.return_value = query
    query.offset.return_value = query
    query.limit.return_value = query
    query.all.return_value = []

    rows = attachment_ledger_dao.get_by_workspace(
        db,
        workspace_id=10,
        transaction_type="ready",
        skip=0,
        limit=50,
    )

    assert rows == []
    db.query.assert_called_once_with(AttachmentLedger)
    assert query.filter.call_count >= 2
    query.offset.assert_called_once_with(0)
    query.limit.assert_called_once_with(50)


def test_dao_get_by_workspace_applies_date_filters() -> None:
    db = MagicMock()
    query = db.query.return_value
    query.filter.return_value = query
    query.order_by.return_value = query
    query.offset.return_value = query
    query.limit.return_value = query
    query.all.return_value = []

    start = datetime.now(timezone.utc) - timedelta(days=7)
    end = datetime.now(timezone.utc)

    attachment_ledger_dao.get_by_workspace(
        db,
        workspace_id=10,
        start_date=start,
        end_date=end,
    )

    assert query.filter.call_count >= 3
