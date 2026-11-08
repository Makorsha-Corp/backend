"""Unit tests for production machine pick policy helpers."""
from unittest.mock import MagicMock, patch

import pytest

from app.utils.production_machine_pick_policy import (
    assert_machine_pick_allowed_for_batch_step,
    machine_has_other_in_progress_step,
    parse_production_machine_pick_policy,
    _visual_kind,
)


def test_parse_policy_defaults_soft():
    assert parse_production_machine_pick_policy(None) == "soft"
    assert parse_production_machine_pick_policy({}) == "soft"
    assert parse_production_machine_pick_policy({"production_machine_pick_policy": "bad"}) == "soft"


def test_parse_policy_reads_value():
    assert parse_production_machine_pick_policy({"production_machine_pick_policy": "block_overlap"}) == (
        "block_overlap"
    )


def test_visual_kind_off_without_event():
    class M:
        is_running = False

    assert _visual_kind(M(), None) == "off"


def test_planned_window_includes_now_helper():
    from app.utils.production_machine_pick_policy import _ranges_overlap
    from datetime import datetime, timezone

    a_start = datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)
    a_end = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    b_start = datetime(2026, 1, 1, 11, 0, tzinfo=timezone.utc)
    b_end = datetime(2026, 1, 1, 13, 0, tzinfo=timezone.utc)
    assert _ranges_overlap(a_start, a_end, b_start, b_end) is True


def test_machine_has_other_in_progress_step_queries_in_progress_logs():
    session = MagicMock()
    base = session.query.return_value.join.return_value.filter.return_value
    base.filter.return_value.first.return_value = None
    assert (
        machine_has_other_in_progress_step(
            session, workspace_id=1, machine_id=5, exclude_stage_log_id=99
        )
        is False
    )
    base.first.return_value = MagicMock(id=100)
    assert (
        machine_has_other_in_progress_step(session, workspace_id=1, machine_id=5) is True
    )


def test_block_overlap_refuses_second_in_progress_not_plan_overlap():
    session = MagicMock()
    machine = MagicMock(is_running=False)
    batch = MagicMock(id=1, planned_start_at=None)
    stage_log = MagicMock(id=10)

    with patch(
        "app.utils.production_machine_pick_policy.machine_activity_manager.get_latest_status",
        return_value=None,
    ), patch(
        "app.utils.production_machine_pick_policy.machine_activity_manager.status_from_activity",
        return_value="IDLE",
    ), patch(
        "app.utils.production_machine_pick_policy.machine_has_other_in_progress_step",
        return_value=True,
    ) as live_check:
        with pytest.raises(ValueError, match="in progress"):
            assert_machine_pick_allowed_for_batch_step(
                session,
                workspace_id=1,
                machine=machine,
                policy="block_overlap",
                batch=batch,
                stage_log=stage_log,
                machine_id=5,
            )
        live_check.assert_called_once_with(
            session,
            workspace_id=1,
            machine_id=5,
            exclude_stage_log_id=10,
        )


def test_block_overlap_allows_when_only_plan_would_overlap():
    session = MagicMock()
    machine = MagicMock(is_running=True)
    batch = MagicMock(id=1, planned_start_at=MagicMock())
    stage_log = MagicMock(id=10)

    with patch(
        "app.utils.production_machine_pick_policy.machine_activity_manager.get_latest_status",
        return_value=None,
    ), patch(
        "app.utils.production_machine_pick_policy.machine_activity_manager.status_from_activity",
        return_value="RUNNING",
    ), patch(
        "app.utils.production_machine_pick_policy.machine_has_other_in_progress_step",
        return_value=False,
    ):
        assert_machine_pick_allowed_for_batch_step(
            session,
            workspace_id=1,
            machine=machine,
            policy="block_overlap",
            batch=batch,
            stage_log=stage_log,
            machine_id=5,
        )
