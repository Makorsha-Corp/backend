"""Production schedule query — timezone-safe window filtering."""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.managers.production_batch_manager import ProductionBatchManager


def _stage_log(log_id: int, minutes: int, machine_id: int, order: int = 1):
    return SimpleNamespace(
        id=log_id,
        stage_name=f"Step {order}",
        stage_order=order,
        production_line_id=8,
        machine_id=machine_id,
        expected_duration_minutes=minutes,
        status="pending",
        rework_of_log_id=None,
    )


def test_get_schedule_draft_with_naive_planned_and_aware_range():
    manager = ProductionBatchManager()
    session = MagicMock()

    batch = SimpleNamespace(
        id=14,
        batch_number="BATCH-2026-012",
        status="draft",
        machine_id=None,
        planned_start_at=datetime(2026, 10, 21, 0, 0),
    )

    query = MagicMock()
    session.query.return_value = query
    query.join.return_value = query
    query.filter.return_value = query
    query.all.return_value = [batch]

    logs = [_stage_log(24, 5, 11, 1), _stage_log(25, 10, 12, 2)]

    with patch.object(manager.stage_log_dao, "get_by_batch", return_value=logs):
        start = datetime(2026, 9, 23, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 11, 5, 0, 0, tzinfo=timezone.utc)
        rows = manager.get_schedule(session, workspace_id=1, factory_id=3, start=start, end=end)

    assert len(rows) == 1
    assert rows[0]["batch_number"] == "BATCH-2026-012"
    assert len(rows[0]["steps"]) == 2
    assert rows[0]["steps"][0]["machine_id"] == 11


def test_get_schedule_skips_draft_whose_window_ended_before_range():
    manager = ProductionBatchManager()
    session = MagicMock()

    batch = SimpleNamespace(
        id=1,
        batch_number="OLD",
        status="draft",
        machine_id=None,
        planned_start_at=datetime(2020, 1, 1, 0, 0),
    )

    query = MagicMock()
    session.query.return_value = query
    query.join.return_value = query
    query.filter.return_value = query
    query.all.return_value = [batch]

    logs = [_stage_log(1, 10, 11)]

    with patch.object(manager.stage_log_dao, "get_by_batch", return_value=logs):
        start = datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 11, 1, 0, 0, tzinfo=timezone.utc)
        rows = manager.get_schedule(session, workspace_id=1, factory_id=3, start=start, end=end)

    assert rows == []


def test_get_schedule_includes_in_progress_without_planned_start_outside_range():
    manager = ProductionBatchManager()
    session = MagicMock()

    batch = SimpleNamespace(
        id=99,
        batch_number="BATCH-LIVE",
        status="in_progress",
        machine_id=11,
        planned_start_at=None,
        started_at=datetime(2026, 10, 24, 6, 0),
        actual_start_time=None,
    )

    query = MagicMock()
    session.query.return_value = query
    query.join.return_value = query
    query.filter.return_value = query
    query.all.return_value = [batch]

    logs = [
        SimpleNamespace(
            id=50,
            stage_name="Card",
            stage_order=1,
            production_line_id=8,
            machine_id=11,
            expected_duration_minutes=60,
            status="in_progress",
            started_at=datetime(2026, 10, 24, 6, 0),
            rework_of_log_id=None,
        ),
    ]

    with patch.object(manager.stage_log_dao, "get_by_batch", return_value=logs):
        start = datetime(2020, 1, 1, 0, 0, tzinfo=timezone.utc)
        end = datetime(2020, 2, 1, 0, 0, tzinfo=timezone.utc)
        rows = manager.get_schedule(session, workspace_id=1, factory_id=3, start=start, end=end)

    assert len(rows) == 1
    assert rows[0]["batch_number"] == "BATCH-LIVE"
    assert rows[0]["steps"][0]["status"] == "in_progress"
    assert rows[0]["steps"][0]["machine_id"] == 11
