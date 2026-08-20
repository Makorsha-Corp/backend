"""Attachment markup overlay tests."""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import Response

from app.dao.attachment_markup import attachment_markup_dao
from app.managers.attachment_manager import AttachmentNotFoundError, AttachmentValidationError
from app.managers.attachment_markup_manager import AttachmentMarkupManager
from app.models.enums import UploadStatusEnum
from app.schemas.attachment_markup import MarkupPayload, PageMarks


def _ready_image(*, attachment_id: int = 1, workspace_id: int = 10):
    attachment = MagicMock()
    attachment.id = attachment_id
    attachment.workspace_id = workspace_id
    attachment.upload_status = UploadStatusEnum.READY.value
    attachment.mime_type = "image/jpeg"
    attachment.format = "jpg"
    return attachment


def _ready_pdf(*, attachment_id: int = 1):
    attachment = _ready_image(attachment_id=attachment_id)
    attachment.mime_type = "application/pdf"
    attachment.format = "pdf"
    return attachment


def _docx_attachment(*, attachment_id: int = 1):
    attachment = _ready_image(attachment_id=attachment_id)
    attachment.mime_type = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    attachment.format = "docx"
    return attachment


def _sample_payload() -> MarkupPayload:
    return MarkupPayload(
        pages={
            "1": PageMarks(
                strokes=[
                    {
                        "color": "#000000",
                        "width": 0.008,
                        "points": [{"x": 0.1, "y": 0.2}, {"x": 0.3, "y": 0.4}],
                    }
                ]
            )
        }
    )


def test_dao_get_for_attachment_filters_workspace() -> None:
    db = MagicMock()
    query = db.query.return_value
    query.filter.return_value = query
    query.order_by.return_value = query
    query.all.return_value = []

    attachment_markup_dao.get_for_attachment(
        db, workspace_id=7, attachment_id=3
    )

    db.query.assert_called_once()
    query.filter.assert_called_once()
    filter_args = query.filter.call_args[0]
    assert len(filter_args) == 2


def test_manager_list_layers_not_found() -> None:
    manager = AttachmentMarkupManager()
    session = MagicMock()

    with patch(
        "app.managers.attachment_markup_manager.attachment_dao.get_active",
        return_value=None,
    ):
        with pytest.raises(AttachmentNotFoundError):
            manager.list_layers(
                session, workspace_id=1, attachment_id=99, current_user_id=5
            )


def test_manager_rejects_non_image_pdf() -> None:
    manager = AttachmentMarkupManager()
    session = MagicMock()

    with patch(
        "app.managers.attachment_markup_manager.attachment_dao.get_active",
        return_value=_docx_attachment(),
    ):
        with pytest.raises(AttachmentValidationError, match="images and PDFs"):
            manager.put_own_layer(
                session,
                workspace_id=1,
                attachment_id=1,
                user_id=5,
                payload=_sample_payload(),
            )


def test_manager_empty_payload_deletes_row() -> None:
    manager = AttachmentMarkupManager()
    session = MagicMock()

    with patch(
        "app.managers.attachment_markup_manager.attachment_dao.get_active",
        return_value=_ready_image(),
    ), patch(
        "app.managers.attachment_markup_manager.attachment_markup_dao.delete_for_user",
        return_value=True,
    ) as delete_mock:
        result = manager.put_own_layer(
            session,
            workspace_id=1,
            attachment_id=1,
            user_id=5,
            payload=MarkupPayload(pages={}),
        )

    assert result is None
    delete_mock.assert_called_once_with(
        session, workspace_id=1, attachment_id=1, user_id=5
    )


def test_manager_list_sets_is_mine() -> None:
    manager = AttachmentMarkupManager()
    session = MagicMock()
    row = MagicMock()
    row.user_id = 5
    row.updated_at = datetime(2026, 8, 20, tzinfo=timezone.utc)
    row.payload = _sample_payload().model_dump()

    profile = MagicMock()
    profile.name = "Alice"

    with patch(
        "app.managers.attachment_markup_manager.attachment_dao.get_active",
        return_value=_ready_pdf(),
    ), patch(
        "app.managers.attachment_markup_manager.attachment_markup_dao.get_for_attachment",
        return_value=[row],
    ), patch(
        "app.managers.attachment_markup_manager.profile_dao.get",
        return_value=profile,
    ):
        layers = manager.list_layers(
            session, workspace_id=1, attachment_id=1, current_user_id=5
        )

    assert len(layers) == 1
    assert layers[0].is_mine is True
    assert layers[0].user_name == "Alice"


def test_manager_put_uses_current_user_only() -> None:
    manager = AttachmentMarkupManager()
    session = MagicMock()
    row = MagicMock()
    row.user_id = 5
    row.updated_at = datetime(2026, 8, 20, tzinfo=timezone.utc)
    row.payload = _sample_payload().model_dump()

    profile = MagicMock()
    profile.name = "Bob"

    with patch(
        "app.managers.attachment_markup_manager.attachment_dao.get_active",
        return_value=_ready_image(),
    ), patch(
        "app.managers.attachment_markup_manager.attachment_markup_dao.upsert_for_user",
        return_value=row,
    ) as upsert_mock, patch(
        "app.managers.attachment_markup_manager.profile_dao.get",
        return_value=profile,
    ):
        manager.put_own_layer(
            session,
            workspace_id=1,
            attachment_id=1,
            user_id=5,
            payload=_sample_payload(),
        )

    upsert_mock.assert_called_once()
    assert upsert_mock.call_args.kwargs["user_id"] == 5


def test_markup_payload_rejects_too_many_points() -> None:
    points = [{"x": 0.1, "y": 0.2}] * 50_001
    with pytest.raises(ValueError, match="maximum"):
        MarkupPayload(
            pages={
                "1": PageMarks(
                    strokes=[{"color": "#000", "width": 0.01, "points": points}]
                )
            }
        )


def test_openapi_markup_paths_registered() -> None:
    from app.main import app

    paths = app.openapi()["paths"]
    assert "/api/v1/attachments/{attachment_id}/markups" in paths
    assert "/api/v1/attachments/{attachment_id}/markups/me" in paths

    put_desc = paths["/api/v1/attachments/{attachment_id}/markups/me"]["put"].get(
        "summary", ""
    ) + paths["/api/v1/attachments/{attachment_id}/markups/me"]["put"].get(
        "description", ""
    )
    assert "sign" not in put_desc.lower()
    assert "signature" not in put_desc.lower()


def test_put_endpoint_returns_204_when_cleared() -> None:
    from app.api.v1.endpoints.attachments import put_my_attachment_markup

    body = MagicMock()
    body.payload = MarkupPayload(pages={})
    workspace = MagicMock(id=1)
    user = MagicMock(id=5)
    db = MagicMock()

    with patch(
        "app.api.v1.endpoints.attachments.attachment_markup_service.put_own_layer",
        return_value=None,
    ):
        result = put_my_attachment_markup(
            attachment_id=1,
            body=body,
            workspace=workspace,
            current_user=user,
            db=db,
        )

    assert isinstance(result, Response)
    assert result.status_code == 204
