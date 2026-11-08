"""Notification entity label resolution."""
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import ProgrammingError

from app.models.enums import AttachmentEntityTypeEnum
from app.utils.notification_entity_label import resolve_notification_entity_label


def test_resolve_label_unknown_entity_type_uses_human_slug() -> None:
    db = MagicMock()
    label = resolve_notification_entity_label(
        db, workspace_id=1, entity_type="inventory", entity_id=12
    )
    assert label == "inventory #12"


def test_resolve_label_survives_db_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*_args, **_kwargs):
        raise ProgrammingError("SELECT", {}, Exception('column "is_tour_sample" does not exist'))

    monkeypatch.setattr(
        "app.utils.notification_entity_label.attachment_manager.resolve_entity_label",
        _boom,
    )
    db = MagicMock()
    label = resolve_notification_entity_label(
        db, workspace_id=1, entity_type=AttachmentEntityTypeEnum.PURCHASE_ORDER.value, entity_id=7
    )
    assert label == "PO-7"
