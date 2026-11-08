"""Discussion activity logging for help tickets."""
from unittest.mock import MagicMock, patch

import pytest

from app.core.exceptions import ValidationError
from app.models.enums import DiscussionEntityType, HelpTicketStatusEnum
from app.models.help_ticket import HelpTicket
from app.schemas.discussion import DiscussionCreate
from app.services.discussion_service import DiscussionService


def _closed_ticket() -> HelpTicket:
    ticket = HelpTicket(
        id=5,
        workspace_id=10,
        ticket_number="HELP-2026-005",
        title="T",
        description="D",
        category=None,
        status=HelpTicketStatusEnum.CLOSED.value,
        type="support",
        created_by=1,
    )
    return ticket


@patch("app.services.discussion_service.help_ticket_dao")
def test_support_ticket_discussion_rejects_closed_ticket(mock_ticket_dao: MagicMock) -> None:
    mock_ticket_dao.get_by_id_and_workspace.return_value = _closed_ticket()
    service = DiscussionService()
    with pytest.raises(ValidationError, match="closed"):
        service.create(
            MagicMock(),
            workspace_id=10,
            user_id=2,
            data=DiscussionCreate(
                entity_type=DiscussionEntityType.support_ticket,
                entity_id=5,
                message="hello",
            ),
        )


@patch("app.managers.help_ticket_manager.help_ticket_manager.log_event")
@patch("app.services.discussion_service.help_ticket_dao")
@patch("app.services.discussion_service.discussion_dao")
def test_support_ticket_discussion_logs_activity(
    mock_discussion_dao: MagicMock,
    mock_ticket_dao: MagicMock,
    mock_log_event: MagicMock,
) -> None:
    open_ticket = _closed_ticket()
    open_ticket.status = HelpTicketStatusEnum.OPENED.value
    mock_ticket_dao.get_by_id_and_workspace.return_value = open_ticket
    discussion = MagicMock()
    discussion.id = 99
    mock_discussion_dao.create.return_value = discussion

    db = MagicMock()
    service = DiscussionService()
    service.create(
        db,
        workspace_id=10,
        user_id=2,
        data=DiscussionCreate(
            entity_type=DiscussionEntityType.support_ticket,
            entity_id=5,
            message="hey there",
        ),
    )

    mock_log_event.assert_called_once()
    assert mock_log_event.call_args.args[3] == "discussion_message"
    assert "hey there" in mock_log_event.call_args.args[4]
    db.commit.assert_called_once()
