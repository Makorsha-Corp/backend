"""Help ticket manager and attachment entity tests."""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.managers.attachment_manager import AttachmentManager
from app.managers.help_ticket_manager import HelpTicketManager, HelpTicketNotFoundError
from app.models.enums import AttachmentEntityTypeEnum, HelpTicketStatusEnum
from app.models.profile import Profile
from app.models.help_ticket import HelpTicket
from app.schemas.attachment import AttachmentSignRequest
from app.schemas.help_ticket import HelpTicketUpdate


def _ticket(**overrides) -> HelpTicket:
    row = HelpTicket(
        id=1,
        workspace_id=10,
        ticket_number="HELP-2026-001",
        title="Login issue",
        description="Cannot sign in on mobile.",
        category="Bug",
        status=HelpTicketStatusEnum.OPEN.value,
        created_by=5,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    for key, value in overrides.items():
        setattr(row, key, value)
    return row


def test_generate_ticket_number_first() -> None:
    from app.dao.help_ticket import DAOHelpTicket

    db = MagicMock()
    db.query.return_value.filter.return_value.count.return_value = 0
    dao = DAOHelpTicket(HelpTicket)
    number = dao.generate_ticket_number(db, workspace_id=10, year=2026)
    assert number == "HELP-2026-001"


def test_generate_ticket_number_increments() -> None:
    from app.dao.help_ticket import DAOHelpTicket

    db = MagicMock()
    db.query.return_value.filter.return_value.count.return_value = 2
    dao = DAOHelpTicket(HelpTicket)
    number = dao.generate_ticket_number(db, workspace_id=10, year=2026)
    assert number == "HELP-2026-003"


@patch("app.managers.help_ticket_manager.help_ticket_dao")
def test_get_by_id_and_workspace_not_found(mock_dao: MagicMock) -> None:
    mock_dao.get_by_id_and_workspace.return_value = None
    manager = HelpTicketManager()
    user = Profile(id=1, name="A", email="a@t.com", user_id="u", hashed_password="x")
    with pytest.raises(HelpTicketNotFoundError):
        manager.get_by_id_and_workspace(
            MagicMock(), ticket_id=99, workspace_id=10, user=user, role="owner"
        )


@patch("app.managers.help_ticket_manager.help_ticket_dao")
@patch("app.managers.help_ticket_manager.utcnow")
def test_close_ticket_sets_closed_fields(mock_utcnow: MagicMock, mock_dao: MagicMock) -> None:
    closed_time = datetime(2026, 8, 13, 12, 0, tzinfo=timezone.utc)
    mock_utcnow.return_value = closed_time
    ticket = _ticket()
    mock_dao.update.return_value = ticket
    manager = HelpTicketManager()
    manager.update_ticket(
        MagicMock(),
        ticket=ticket,
        payload=HelpTicketUpdate(status=HelpTicketStatusEnum.CLOSED),
        user_id=7,
    )
    mock_dao.update.assert_called_once()
    update_arg = mock_dao.update.call_args.kwargs["obj_in"]
    assert update_arg["status"] == HelpTicketStatusEnum.CLOSED.value
    assert update_arg["closed_at"] == closed_time
    assert update_arg["closed_by"] == 7


@patch("app.managers.help_ticket_manager.help_ticket_dao")
def test_reopen_ticket_clears_closed_fields(mock_dao: MagicMock) -> None:
    ticket = _ticket(
        status=HelpTicketStatusEnum.CLOSED.value,
        closed_at=datetime.now(timezone.utc),
        closed_by=7,
    )
    mock_dao.update.return_value = ticket
    manager = HelpTicketManager()
    manager.update_ticket(
        MagicMock(),
        ticket=ticket,
        payload=HelpTicketUpdate(status=HelpTicketStatusEnum.OPEN),
        user_id=7,
    )
    update_arg = mock_dao.update.call_args.kwargs["obj_in"]
    assert update_arg["status"] == HelpTicketStatusEnum.OPEN.value
    assert update_arg["closed_at"] is None
    assert update_arg["closed_by"] is None


@patch("app.managers.attachment_manager.help_ticket_dao")
def test_resolve_entity_label_support_ticket(mock_dao: MagicMock) -> None:
    mock_dao.get_by_id_and_workspace.return_value = _ticket(ticket_number="HELP-2026-042")
    manager = AttachmentManager()
    label = manager.resolve_entity_label(
        MagicMock(),
        workspace_id=10,
        entity_type=AttachmentEntityTypeEnum.SUPPORT_TICKET,
        entity_id=1,
    )
    assert label == "HELP-2026-042"


@patch("app.managers.attachment_manager.help_ticket_dao")
def test_resolve_entity_label_support_ticket_fallback(mock_dao: MagicMock) -> None:
    mock_dao.get_by_id_and_workspace.return_value = None
    manager = AttachmentManager()
    label = manager.resolve_entity_label(
        MagicMock(),
        workspace_id=10,
        entity_type=AttachmentEntityTypeEnum.SUPPORT_TICKET,
        entity_id=99,
    )
    assert label == "support_ticket-99"


def test_attachment_sign_accepts_support_ticket_entity() -> None:
    manager = AttachmentManager()
    payload = AttachmentSignRequest(
        entity_type=AttachmentEntityTypeEnum.SUPPORT_TICKET,
        entity_id=1,
        file_name="screenshot.png",
        mime_type="image/png",
        file_size=2048,
    )
    normalized = manager.normalize_upload_request(payload)
    assert normalized.file_name == "screenshot.png"
    assert normalized.mime_type == "image/png"


def test_support_ticket_folder_label() -> None:
    from app.managers.attachment_manager import ENTITY_TYPE_FOLDER_LABELS

    assert (
        ENTITY_TYPE_FOLDER_LABELS[AttachmentEntityTypeEnum.SUPPORT_TICKET]
        == "Help Tickets"
    )
