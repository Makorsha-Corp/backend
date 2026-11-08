"""Read-time metrics and planned windows for production stage logs."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional


def duration_minutes(started_at: Optional[datetime], completed_at: Optional[datetime]) -> Optional[int]:
    if started_at is None or completed_at is None:
        return None
    seconds = (completed_at - started_at).total_seconds()
    if seconds < 0:
        return None
    return int(seconds // 60)


def compute_stage_metrics(
    *,
    started_at: Optional[datetime],
    completed_at: Optional[datetime],
    expected_duration_minutes: Optional[int],
    expected_output_quantity: Optional[int],
    input_quantity: Optional[int],
    output_quantity: Optional[int],
    waste_quantity: Optional[int],
) -> dict:
    """Missing inputs leave that metric null. Nothing is stored."""
    actual = duration_minutes(started_at, completed_at)
    output = float(output_quantity) if output_quantity is not None else None
    expected_output = float(expected_output_quantity) if expected_output_quantity else None
    waste = float(waste_quantity) if waste_quantity is not None else None
    input_qty = float(input_quantity) if input_quantity else None
    yield_pct = None
    if output is not None and expected_output:
        yield_pct = round(output / expected_output * 100, 2)
    time_efficiency_pct = None
    if expected_duration_minutes and actual:
        time_efficiency_pct = round(expected_duration_minutes / actual * 100, 2)
    throughput_per_hour = None
    if output is not None and actual:
        throughput_per_hour = round(output / (actual / 60), 2)
    waste_pct = None
    if waste is not None:
        denom = input_qty
        if not denom and output is not None:
            denom = output + waste
        if denom:
            waste_pct = round(waste / denom * 100, 2)
    return {
        "actual_duration_minutes": actual,
        "yield_pct": yield_pct,
        "time_efficiency_pct": time_efficiency_pct,
        "throughput_per_hour": throughput_per_hour,
        "waste_pct": waste_pct,
    }


def attach_stage_metrics(log) -> object:
    metrics = compute_stage_metrics(
        started_at=log.started_at,
        completed_at=log.completed_at,
        expected_duration_minutes=log.expected_duration_minutes,
        expected_output_quantity=log.expected_output_quantity,
        input_quantity=log.input_quantity,
        output_quantity=log.output_quantity,
        waste_quantity=log.waste_quantity,
    )
    for key, value in metrics.items():
        setattr(log, key, value)
    return log


def planned_end_at(planned_start_at: Optional[datetime], expected_minutes: int) -> Optional[datetime]:
    if planned_start_at is None:
        return None
    return planned_start_at + timedelta(minutes=max(expected_minutes, 0))


def ordered_stage_logs(logs: list) -> list:
    return sorted(logs, key=lambda row: (row.stage_order, row.id))


def logs_have_stored_planned_starts(logs: list) -> bool:
    ordered = ordered_stage_logs(logs)
    return bool(ordered) and all(getattr(log, "planned_start_at", None) is not None for log in ordered)


def assign_sequential_planned_starts(anchor: datetime, logs: list) -> None:
    """Write planned_start_at on each log from anchor (mutates log objects)."""
    cursor = anchor
    for log in ordered_stage_logs(logs):
        log.planned_start_at = cursor
        cursor = cursor + timedelta(minutes=log.expected_duration_minutes or 0)


def step_planned_end(log, start: Optional[datetime] = None) -> Optional[datetime]:
    when = start if start is not None else getattr(log, "planned_start_at", None)
    if when is None:
        return None
    return when + timedelta(minutes=log.expected_duration_minutes or 0)


def _window_row(log, start: datetime) -> dict:
    minutes = log.expected_duration_minutes or 0
    end = start + timedelta(minutes=minutes)
    return {
        "stage_log_id": log.id,
        "stage_name": log.stage_name,
        "stage_order": log.stage_order,
        "production_line_id": log.production_line_id,
        "machine_id": log.machine_id,
        "status": getattr(log, "status", "pending"),
        "planned_start_at": start,
        "planned_end_at": end,
        "rework_of_log_id": log.rework_of_log_id,
    }


def step_planned_windows(planned_start_at: Optional[datetime], logs: list) -> list[dict]:
    """Planned windows: stored per-log starts when present, else sequential from anchor."""
    ordered = ordered_stage_logs(logs)
    if not ordered:
        return []
    if logs_have_stored_planned_starts(ordered):
        return [_window_row(log, log.planned_start_at) for log in ordered]
    if planned_start_at is None:
        return []
    cursor = planned_start_at
    windows = []
    for log in ordered:
        windows.append(_window_row(log, cursor))
        cursor = cursor + timedelta(minutes=log.expected_duration_minutes or 0)
    return windows
