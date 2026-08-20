"""Help ticket visibility and platform admin tests."""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.managers.help_ticket_manager import (
    HelpTicketForbiddenError,
    HelpTicketManager,
    HelpTicketNotFoundError,
)
from app.models.enums import HelpTicketStatusEnum
from app.models.help_ticket import HelpTicket
from app.models.profile import Profile


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


def _user(*, user_id: int = 5, is_platform_admin: bool = False) -> Profile:
    user = Profile(id=user_id, name="Test User", email="test@example.com", user_id="u1", hashed_password="x")
    user.is_platform_admin = is_platform_admin
    return user


def test_can_view_all_tickets_owner_and_manager() -> None:
    manager = HelpTicketManager()
    assert manager.can_view_all_tickets("owner") is True
    assert manager.can_view_all_tickets("ground-team-manager") is True
    assert manager.can_view_all_tickets("ground-team") is False
    assert manager.can_view_all_tickets("finance") is False


def test_can_access_ticket_creator_vs_other() -> None:
    manager = HelpTicketManager()
    ticket = _ticket(created_by=5)
    creator = _user(user_id=5)
    other = _user(user_id=9)
    assert manager.can_access_ticket(ticket=ticket, user=creator, role="ground-team") is True
    assert manager.can_access_ticket(ticket=ticket, user=other, role="ground-team") is False
    assert manager.can_access_ticket(ticket=ticket, user=other, role="owner") is True


def test_can_access_ticket_platform_admin() -> None:
    manager = HelpTicketManager()
    ticket = _ticket(created_by=5)
    admin = _user(user_id=99, is_platform_admin=True)
    assert manager.can_access_ticket(ticket=ticket, user=admin, role=None) is True


@patch("app.managers.help_ticket_manager.help_ticket_dao")
def test_get_by_id_forbidden_for_non_creator(mock_dao: MagicMock) -> None:
    mock_dao.get_by_id_and_workspace.return_value = _ticket(created_by=5)
    manager = HelpTicketManager()
    with pytest.raises(HelpTicketForbiddenError):
        manager.get_by_id_and_workspace(
            MagicMock(),
            ticket_id=1,
            workspace_id=10,
            user=_user(user_id=9),
            role="ground-team",
        )


@patch("app.managers.help_ticket_manager.help_ticket_dao")
def test_list_tickets_filters_created_by_for_ground_team(mock_dao: MagicMock) -> None:
    mock_dao.list_by_workspace.return_value = []
    manager = HelpTicketManager()
    user = _user(user_id=7)
    manager.list_tickets(
        MagicMock(),
        workspace_id=10,
        user=user,
        role="ground-team",
    )
    mock_dao.list_by_workspace.assert_called_once()
    assert mock_dao.list_by_workspace.call_args.kwargs["created_by"] == 7


@patch("app.managers.help_ticket_manager.help_ticket_dao")
def test_list_tickets_no_creator_filter_for_owner(mock_dao: MagicMock) -> None:
    mock_dao.list_by_workspace.return_value = []
    manager = HelpTicketManager()
    user = _user(user_id=7)
    manager.list_tickets(
        MagicMock(),
        workspace_id=10,
        user=user,
        role="owner",
    )
    assert mock_dao.list_by_workspace.call_args.kwargs["created_by"] is None


@patch("app.managers.help_ticket_manager.help_ticket_dao")
def test_get_by_id_not_found(mock_dao: MagicMock) -> None:
    mock_dao.get_by_id_and_workspace.return_value = None
    manager = HelpTicketManager()
    with pytest.raises(HelpTicketNotFoundError):
        manager.get_by_id_and_workspace(
            MagicMock(),
            ticket_id=99,
            workspace_id=10,
            user=_user(),
            role="owner",
        )


def test_to_platform_item_merges_creator_name_without_duplicate_kwargs() -> None:
    """Regression: creator_name must not be passed twice to PlatformHelpTicketListItem."""
    manager = HelpTicketManager()
    ticket = _ticket(created_by=5)
    creator = Profile(id=5, name="Jane Creator", email="j@t.com", user_id="u5", hashed_password="x")
    ticket.creator = creator

    item = manager._to_platform_item(ticket, "Acme Mill", "Jane Creator")

    assert item.workspace_name == "Acme Mill"
    assert item.creator_name == "Jane Creator"
    assert item.ticket_number == "HELP-2026-001"


def test_platform_help_tickets_endpoint_returns_200_for_admin() -> None:
    from fastapi.testclient import TestClient

    from app.core.deps import get_platform_admin
    from app.main import app

    admin = _user(user_id=1, is_platform_admin=True)
    app.dependency_overrides[get_platform_admin] = lambda: admin
    try:
        client = TestClient(app)
        response = client.get("/api/v1/platform/help/tickets")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
    finally:
        app.dependency_overrides.clear()


def test_platform_help_tickets_endpoint_returns_403_for_non_admin() -> None:
    from fastapi.testclient import TestClient

    from app.core.deps import get_current_active_user
    from app.main import app

    non_admin = _user(user_id=2, is_platform_admin=False)
    app.dependency_overrides[get_current_active_user] = lambda: non_admin
    try:
        client = TestClient(app)
        response = client.get("/api/v1/platform/help/tickets")
        assert response.status_code == 403
        assert "Platform admin" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()
