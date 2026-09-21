"""Help ticket manager and attachment entity tests."""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.managers.attachment_manager import AttachmentManager
from app.managers.help_ticket_manager import (
    HelpTicketInvalidTransitionError,
    HelpTicketManager,
    HelpTicketNotFoundError,
    HelpTicketStatusChangeForbiddenError,
)
from app.models.enums import AttachmentEntityTypeEnum, HelpTicketStatusEnum, HelpTicketTypeEnum
from app.models.profile import Profile
from app.models.help_ticket import HelpTicket
from app.schemas.attachment import AttachmentSignRequest
from app.schemas.help_ticket import HelpTicketCreate, HelpTicketUpdate


def _ticket(**overrides) -> HelpTicket:
    row = HelpTicket(
        id=1,
        workspace_id=10,
        ticket_number="HELP-2026-001",
        title="Login issue",
        description="Cannot sign in on mobile.",
        category="Bug",
        status=HelpTicketStatusEnum.PENDING.value,
        type=HelpTicketTypeEnum.SUPPORT.value,
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
def test_open_ticket_from_pending(mock_utcnow: MagicMock, mock_dao: MagicMock) -> None:
    ticket = _ticket(status=HelpTicketStatusEnum.PENDING.value)
    mock_dao.update.return_value = ticket
    manager = HelpTicketManager()
    manager.update_ticket(
        MagicMock(),
        ticket=ticket,
        payload=HelpTicketUpdate(status=HelpTicketStatusEnum.OPENED),
        user_id=7,
        is_platform_admin=True,
    )
    update_arg = mock_dao.update.call_args.kwargs["obj_in"]
    assert update_arg["status"] == HelpTicketStatusEnum.OPENED.value
    assert "closed_at" not in update_arg
    assert "closed_by" not in update_arg


@patch("app.managers.help_ticket_manager.help_ticket_dao")
@patch("app.managers.help_ticket_manager.utcnow")
def test_close_ticket_sets_closed_fields(mock_utcnow: MagicMock, mock_dao: MagicMock) -> None:
    closed_time = datetime(2026, 8, 13, 12, 0, tzinfo=timezone.utc)
    mock_utcnow.return_value = closed_time
    ticket = _ticket(status=HelpTicketStatusEnum.OPENED.value)
    mock_dao.update.return_value = ticket
    manager = HelpTicketManager()
    manager.update_ticket(
        MagicMock(),
        ticket=ticket,
        payload=HelpTicketUpdate(status=HelpTicketStatusEnum.CLOSED),
        user_id=7,
        is_platform_admin=True,
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
        payload=HelpTicketUpdate(status=HelpTicketStatusEnum.OPENED),
        user_id=7,
        is_platform_admin=True,
    )
    update_arg = mock_dao.update.call_args.kwargs["obj_in"]
    assert update_arg["status"] == HelpTicketStatusEnum.OPENED.value
    assert update_arg["closed_at"] is None
    assert update_arg["closed_by"] is None


@patch("app.managers.help_ticket_manager.help_ticket_dao")
def test_mill_user_cannot_change_status(mock_dao: MagicMock) -> None:
    ticket = _ticket(status=HelpTicketStatusEnum.PENDING.value)
    manager = HelpTicketManager()
    with pytest.raises(HelpTicketStatusChangeForbiddenError):
        manager.update_ticket(
            MagicMock(),
            ticket=ticket,
            payload=HelpTicketUpdate(status=HelpTicketStatusEnum.OPENED),
            user_id=5,
            is_platform_admin=False,
        )
    mock_dao.update.assert_not_called()


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (HelpTicketStatusEnum.PENDING, HelpTicketStatusEnum.CLOSED),
        (HelpTicketStatusEnum.OPENED, HelpTicketStatusEnum.PENDING),
        (HelpTicketStatusEnum.CLOSED, HelpTicketStatusEnum.PENDING),
        (HelpTicketStatusEnum.CLOSED, HelpTicketStatusEnum.CLOSED),
    ],
)
@patch("app.managers.help_ticket_manager.help_ticket_dao")
def test_invalid_status_transition_rejected(
    mock_dao: MagicMock,
    current: HelpTicketStatusEnum,
    target: HelpTicketStatusEnum,
) -> None:
    ticket = _ticket(status=current.value)
    manager = HelpTicketManager()
    with pytest.raises(HelpTicketInvalidTransitionError):
        manager.update_ticket(
            MagicMock(),
            ticket=ticket,
            payload=HelpTicketUpdate(status=target),
            user_id=7,
            is_platform_admin=True,
        )
    mock_dao.update.assert_not_called()


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


# ---------------- Type field tests ----------------


def test_create_schema_defaults_type_to_support() -> None:
    """HelpTicketCreate defaults type to 'support' when omitted."""
    payload = HelpTicketCreate(title="Bug", description="Something broke")
    assert payload.type == HelpTicketTypeEnum.SUPPORT


def test_create_schema_accepts_feedback_type() -> None:
    """HelpTicketCreate accepts explicit type=feedback."""
    payload = HelpTicketCreate(
        title="Feature idea",
        description="Add dark mode",
        type=HelpTicketTypeEnum.FEEDBACK,
    )
    assert payload.type == HelpTicketTypeEnum.FEEDBACK


def test_update_schema_excludes_type() -> None:
    """HelpTicketUpdate should NOT have a 'type' field."""
    assert "type" not in HelpTicketUpdate.model_fields


@patch("app.managers.help_ticket_manager.help_ticket_dao")
def test_list_tickets_passes_type_filter(mock_dao: MagicMock) -> None:
    """Manager list_tickets passes ticket_type to DAO."""
    mock_dao.list_by_workspace.return_value = []
    manager = HelpTicketManager()
    user = Profile(id=1, name="A", email="a@t.com", user_id="u", hashed_password="x")
    manager.list_tickets(
        MagicMock(),
        workspace_id=10,
        user=user,
        role="owner",
        ticket_type=HelpTicketTypeEnum.FEEDBACK,
    )
    mock_dao.list_by_workspace.assert_called_once()
    assert mock_dao.list_by_workspace.call_args.kwargs["ticket_type"] == "feedback"


@patch("app.managers.help_ticket_manager.help_ticket_dao")
def test_list_tickets_no_type_filter_when_none(mock_dao: MagicMock) -> None:
    """Manager list_tickets passes None ticket_type when not specified."""
    mock_dao.list_by_workspace.return_value = []
    manager = HelpTicketManager()
    user = Profile(id=1, name="A", email="a@t.com", user_id="u", hashed_password="x")
    manager.list_tickets(
        MagicMock(),
        workspace_id=10,
        user=user,
        role="owner",
    )
    mock_dao.list_by_workspace.assert_called_once()
    assert mock_dao.list_by_workspace.call_args.kwargs["ticket_type"] is None


def test_to_response_includes_type() -> None:
    """HelpTicketManager.to_response includes type field."""
    ticket = _ticket(type=HelpTicketTypeEnum.FEEDBACK.value)
    manager = HelpTicketManager()
    response = manager.to_response(ticket)
    assert response.type == HelpTicketTypeEnum.FEEDBACK


def test_dao_create_with_user_persists_type() -> None:
    """DAO create_with_user persists type from payload."""
    from app.dao.help_ticket import DAOHelpTicket

    db = MagicMock()
    db.query.return_value.filter.return_value.count.return_value = 0
    dao = DAOHelpTicket(HelpTicket)

    payload = HelpTicketCreate(
        title="Feedback item",
        description="Improve UX",
        type=HelpTicketTypeEnum.FEEDBACK,
    )
    ticket = dao.create_with_user(db, obj_in=payload, workspace_id=10, user_id=5)
    assert ticket.type == "feedback"


def test_dao_create_with_user_defaults_type_to_support() -> None:
    """DAO create_with_user defaults type to 'support'."""
    from app.dao.help_ticket import DAOHelpTicket

    db = MagicMock()
    db.query.return_value.filter.return_value.count.return_value = 0
    dao = DAOHelpTicket(HelpTicket)

    payload = HelpTicketCreate(title="Bug", description="Something broke")
    ticket = dao.create_with_user(db, obj_in=payload, workspace_id=10, user_id=5)
    assert ticket.type == "support"


def test_dao_create_with_user_sets_status_pending() -> None:
    """DAO create_with_user always sets status to pending."""
    from app.dao.help_ticket import DAOHelpTicket

    db = MagicMock()
    db.query.return_value.filter.return_value.count.return_value = 0
    dao = DAOHelpTicket(HelpTicket)

    payload = HelpTicketCreate(title="Bug", description="Something broke")
    ticket = dao.create_with_user(db, obj_in=payload, workspace_id=10, user_id=5)
    assert ticket.status == HelpTicketStatusEnum.PENDING.value


@patch("app.managers.help_ticket_manager.help_ticket_dao")
def test_list_tickets_passes_status_filter(mock_dao: MagicMock) -> None:
    mock_dao.list_by_workspace.return_value = []
    manager = HelpTicketManager()
    user = Profile(id=1, name="A", email="a@t.com", user_id="u", hashed_password="x")
    manager.list_tickets(
        MagicMock(),
        workspace_id=10,
        user=user,
        role="owner",
        status=HelpTicketStatusEnum.OPENED,
    )
    assert mock_dao.list_by_workspace.call_args.kwargs["status"] == "opened"


def test_help_tickets_endpoint_rejects_mill_user_status_patch() -> None:
    from fastapi.testclient import TestClient

    from app.core.deps import get_current_active_user, get_current_workspace, get_db
    from app.main import app
    from app.models.workspace import Workspace

    user = Profile(id=5, name="Mill User", email="m@t.com", user_id="u5", hashed_password="x")
    user.is_platform_admin = False
    workspace = Workspace(id=10, name="Acme", slug="acme")

    db = MagicMock()

    app.dependency_overrides[get_current_active_user] = lambda: user
    app.dependency_overrides[get_current_workspace] = lambda: workspace
    app.dependency_overrides[get_db] = lambda: db
    try:
        with patch(
            "app.api.v1.endpoints.help_tickets.help_ticket_service.update_ticket",
            side_effect=HelpTicketStatusChangeForbiddenError("Only platform admins may change ticket status."),
        ):
            client = TestClient(app)
            response = client.patch(
                "/api/v1/help/tickets/1",
                json={"status": "opened"},
            )
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()
