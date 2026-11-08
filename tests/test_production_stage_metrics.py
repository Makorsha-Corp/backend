"""Read-time production step metrics."""
from datetime import datetime, timedelta

from app.utils.production_stage_metrics import (
    assign_sequential_planned_starts,
    compute_stage_metrics,
    planned_end_at,
    step_planned_windows,
)


def test_metrics_null_when_inputs_missing():
    metrics = compute_stage_metrics(
        started_at=None,
        completed_at=None,
        expected_duration_minutes=None,
        expected_output_quantity=None,
        input_quantity=None,
        output_quantity=None,
        waste_quantity=None,
    )
    assert metrics == {
        "actual_duration_minutes": None,
        "yield_pct": None,
        "time_efficiency_pct": None,
        "throughput_per_hour": None,
        "waste_pct": None,
    }


def test_metrics_math():
    start = datetime(2026, 9, 27, 8, 0)
    end = start + timedelta(minutes=120)
    metrics = compute_stage_metrics(
        started_at=start,
        completed_at=end,
        expected_duration_minutes=60,
        expected_output_quantity=100,
        input_quantity=80,
        output_quantity=50,
        waste_quantity=20,
    )
    assert metrics["actual_duration_minutes"] == 120
    assert metrics["yield_pct"] == 50
    assert metrics["time_efficiency_pct"] == 50
    assert metrics["throughput_per_hour"] == 25
    assert metrics["waste_pct"] == 25


def test_waste_falls_back_to_output_plus_waste():
    metrics = compute_stage_metrics(
        started_at=None,
        completed_at=None,
        expected_duration_minutes=None,
        expected_output_quantity=None,
        input_quantity=None,
        output_quantity=40,
        waste_quantity=10,
    )
    assert metrics["waste_pct"] == 20


def test_planned_windows_are_sequential():
    start = datetime(2026, 9, 27, 9, 0)

    class Log:
        def __init__(self, id, order, minutes, line_id, machine_id, planned_start_at=None):
            self.id = id
            self.stage_order = order
            self.expected_duration_minutes = minutes
            self.stage_name = f"S{order}"
            self.production_line_id = line_id
            self.machine_id = machine_id
            self.rework_of_log_id = None
            self.planned_start_at = planned_start_at

    windows = step_planned_windows(start, [Log(2, 2, 30, 8, 3), Log(1, 1, 60, 7, 2)])
    assert windows[0]["planned_start_at"] == start
    assert windows[0]["planned_end_at"] == start + timedelta(minutes=60)
    assert windows[1]["planned_start_at"] == start + timedelta(minutes=60)
    assert planned_end_at(start, 90) == start + timedelta(minutes=90)


def test_stored_planned_starts_override_anchor_chain():
    start = datetime(2026, 9, 27, 9, 0)
    gap_start = start + timedelta(days=2)

    class Log:
        def __init__(self, id, order, minutes, planned_start_at):
            self.id = id
            self.stage_order = order
            self.expected_duration_minutes = minutes
            self.stage_name = f"S{order}"
            self.production_line_id = 1
            self.machine_id = 1
            self.rework_of_log_id = None
            self.status = "pending"
            self.planned_start_at = planned_start_at

    logs = [Log(1, 1, 60, start), Log(2, 2, 30, gap_start)]
    windows = step_planned_windows(start, logs)
    assert windows[1]["planned_start_at"] == gap_start
    assert windows[0]["planned_start_at"] == start
