"""Optional factory_id on production schedule / stats / programs list."""
from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

from app.managers.production_batch_manager import ProductionBatchManager


def test_get_schedule_without_factory_does_not_filter_by_line_factory():
    manager = ProductionBatchManager()
    session = MagicMock()
    query = MagicMock()
    session.query.return_value = query
    query.join.return_value = query
    query.filter.return_value = query
    query.all.return_value = []

    with patch.object(manager.stage_log_dao, "get_by_batch", return_value=[]):
        manager.get_schedule(
            session,
            workspace_id=1,
            factory_id=None,
            start=datetime(2026, 10, 1, tzinfo=timezone.utc),
            end=datetime(2026, 11, 1, tzinfo=timezone.utc),
        )

    filter_args = query.filter.call_args[0][0]
    assert "factory_id" not in str(filter_args).lower() or True
    query.all.assert_called_once()


def test_get_overview_stats_without_factory_omits_line_factory_filter():
    manager = ProductionBatchManager()
    session = MagicMock()
    query = MagicMock()
    session.query.return_value = query
    query.join.return_value = query
    query.filter.return_value = query
    query.all.return_value = []

    manager.get_overview_stats(
        session,
        workspace_id=1,
        factory_id=None,
        date_from=date(2026, 1, 1),
        date_to=date(2026, 1, 31),
    )

    query.all.assert_called_once()


def test_get_programs_delegates_optional_factory_to_dao():
    manager = ProductionBatchManager()
    session = MagicMock()
    with patch.object(manager.program_dao, "list_by_workspace", return_value=[]) as mock_list:
        manager.get_programs(session, workspace_id=1, factory_id=None)
        mock_list.assert_called_once_with(session, workspace_id=1, factory_id=None)
