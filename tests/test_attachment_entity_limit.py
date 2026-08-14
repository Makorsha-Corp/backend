"""Per-entity attachment cap enforcement."""
from unittest.mock import MagicMock, patch

import pytest

from app.managers.attachment_manager import AttachmentLimitError, AttachmentManager
from app.models.enums import AttachmentEntityTypeEnum
from app.schemas.attachment import AttachmentSignRequest


def _sign_payload(**overrides) -> AttachmentSignRequest:
    data = {
        "entity_type": AttachmentEntityTypeEnum.PURCHASE_ORDER,
        "entity_id": 42,
        "file_name": "invoice.pdf",
        "mime_type": "application/pdf",
        "file_size": 1024,
    }
    data.update(overrides)
    return AttachmentSignRequest(**data)


@patch("app.managers.attachment_manager.settings")
@patch("app.managers.attachment_manager.attachment_link_dao")
def test_assert_capacity_raises_at_limit(mock_dao: MagicMock, mock_settings: MagicMock) -> None:
    mock_settings.MAX_ATTACHMENTS_PER_ENTITY = 25
    mock_dao.count_linked_attachments_for_entity.return_value = 25
    manager = AttachmentManager()
    with pytest.raises(AttachmentLimitError, match="maximum of 25"):
        manager.assert_entity_attachment_capacity(
            MagicMock(),
            workspace_id=10,
            entity_type=AttachmentEntityTypeEnum.PURCHASE_ORDER,
            entity_id=42,
        )


@patch("app.managers.attachment_manager.settings")
@patch("app.managers.attachment_manager.attachment_link_dao")
def test_assert_capacity_allows_below_limit(mock_dao: MagicMock, mock_settings: MagicMock) -> None:
    mock_settings.MAX_ATTACHMENTS_PER_ENTITY = 25
    mock_dao.count_linked_attachments_for_entity.return_value = 24
    manager = AttachmentManager()
    manager.assert_entity_attachment_capacity(
        MagicMock(),
        workspace_id=10,
        entity_type=AttachmentEntityTypeEnum.PURCHASE_ORDER,
        entity_id=42,
    )


@patch("app.managers.attachment_manager.settings")
@patch("app.managers.attachment_manager.attachment_link_dao")
@patch("app.managers.attachment_manager.attachment_dao")
@patch("app.managers.attachment_manager.attachment_ledger_dao")
def test_create_pending_raises_when_at_capacity(
    mock_ledger_dao: MagicMock,
    mock_attachment_dao: MagicMock,
    mock_link_dao: MagicMock,
    mock_settings: MagicMock,
) -> None:
    mock_settings.MAX_ATTACHMENTS_PER_ENTITY = 25
    mock_link_dao.count_linked_attachments_for_entity.return_value = 25
    manager = AttachmentManager()
    normalized = manager.normalize_upload_request(_sign_payload())
    user = MagicMock()
    user.id = 5
    with pytest.raises(AttachmentLimitError):
        manager.create_pending_attachment(
            MagicMock(),
            workspace_id=10,
            user=user,
            payload=_sign_payload(),
            normalized=normalized,
            stored_public_id="ws-10/abc",
            asset_folder="Dev/Test",
        )
