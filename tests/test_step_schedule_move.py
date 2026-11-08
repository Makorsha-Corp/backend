"""Step schedule board — clamp, push, and stored planned starts."""
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.managers.production_batch_manager import ProductionBatchManager
from app.utils.production_stage_metrics import assign_sequential_planned_starts, step_planned_windows
from app.utils.step_schedule_move import compute_move_planned_start_updates


def _log(log_id, order, minutes, *, status="pending", start=None):
    return SimpleNamespace(
        id=log_id,
        stage_order=order,
        expected_duration_minutes=minutes,
        stage_name=f"S{order}",
        production_line_id=1,
        machine_id=1,
        rework_of_log_id=None,
        status=status,
        planned_start_at=start,
    )


def test_backfill_matches_sequential_windows():
    anchor = datetime(2026, 10, 21, 9, 0)
    logs = [_log(1, 1, 60), _log(2, 2, 30)]
    assign_sequential_planned_starts(anchor, logs)
    stored = step_planned_windows(anchor, logs)
    sequential = step_planned_windows(anchor, [_log(1, 1, 60), _log(2, 2, 30)])
    for left, right in zip(stored, sequential):
        assert left["planned_start_at"] == right["planned_start_at"]
        assert left["planned_end_at"] == right["planned_end_at"]


def test_drag_step2_earlier_clamps_to_step1_end():
    t0 = datetime(2026, 10, 21, 9, 0)
    logs = [_log(1, 1, 60, start=t0), _log(2, 2, 30, start=t0 + timedelta(hours=2))]
    updates = compute_move_planned_start_updates(logs, 2, t0 + timedelta(minutes=30))
    assert updates[2] == t0 + timedelta(minutes=60)


def test_drag_step1_later_pushes_step2_gap_preserved_on_step3():
    t0 = datetime(2026, 10, 21, 9, 0)
    t2 = t0 + timedelta(hours=4)
    t3 = t0 + timedelta(hours=8)
    logs = [
        _log(1, 1, 60, start=t0),
        _log(2, 2, 30, start=t0 + timedelta(minutes=60)),
        _log(3, 3, 45, start=t3),
    ]
    later = t0 + timedelta(hours=1)
    updates = compute_move_planned_start_updates(logs, 1, later)
    assert updates[1] == later
    assert updates[2] == later + timedelta(minutes=60)
    assert 3 not in updates


def test_move_rejects_non_pending_step():
    manager = ProductionBatchManager()
    session = MagicMock()
    log = SimpleNamespace(
        id=5,
        batch_id=1,
        status="in_progress",
        stage_order=1,
        workspace_id=1,
    )
    with patch.object(manager, "_require_stage_log", return_value=log):
        with pytest.raises(ValueError, match="Only pending"):
            manager.move_stage_log_on_schedule(
                session,
                5,
                1,
                99,
                production_line_id=2,
                planned_start_at=datetime(2026, 10, 21, 9, 0),
            )


def test_get_schedule_uses_stored_step_start():
    manager = ProductionBatchManager()
    session = MagicMock()
    anchor = datetime(2026, 10, 21, 0, 0)
    custom = datetime(2026, 10, 22, 14, 0)

    batch = SimpleNamespace(
        id=14,
        batch_number="BATCH-2026-012",
        status="draft",
        machine_id=None,
        planned_start_at=anchor,
    )

    query = MagicMock()
    session.query.return_value = query
    query.join.return_value = query
    query.filter.return_value = query
    query.all.return_value = [batch]

    logs = [
        SimpleNamespace(
            id=24,
            stage_name="Step 1",
            stage_order=1,
            production_line_id=8,
            machine_id=11,
            expected_duration_minutes=5,
            status="pending",
            rework_of_log_id=None,
            planned_start_at=custom,
        ),
    ]

    with patch.object(manager.stage_log_dao, "get_by_batch", return_value=logs):
        from datetime import timezone

        start = datetime(2026, 9, 23, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 11, 5, 0, 0, tzinfo=timezone.utc)
        rows = manager.get_schedule(session, workspace_id=1, factory_id=3, start=start, end=end)

    assert rows[0]["steps"][0]["planned_start_at"] == custom
