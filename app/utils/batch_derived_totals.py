"""Batch header totals computed from steps. Nothing here is stored on the batch row."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional, Sequence

from app.utils.production_stage_metrics import duration_minutes
from app.utils.time import utcnow


def _last_log(logs: Sequence[Any]) -> Any | None:
    if not logs:
        return None
    return max(logs, key=lambda row: (getattr(row, "stage_order", 0), getattr(row, "id", 0)))


def _match_batch_item(batch_items: Sequence[Any], item_id: int, item_role: str) -> Any | None:
    for row in batch_items:
        if row.item_id == item_id and row.item_role == item_role:
            return row
    return None


def _output_quantities(
    log: Any,
    batch_items: Sequence[Any],
    formula_stage_items: Sequence[Any],
) -> tuple[Optional[Decimal], Optional[Decimal]]:
    stage_id = getattr(log, "formula_stage_id", None)
    if stage_id is not None:
        defs = [
            row
            for row in formula_stage_items
            if row.formula_stage_id == stage_id and row.item_role == "output"
        ]
        if not defs:
            return None, None
        expected = Decimal("0")
        actual = Decimal("0")
        any_actual = False
        for formula_row in defs:
            batch_item = _match_batch_item(batch_items, formula_row.item_id, "output")
            if batch_item is not None and batch_item.expected_quantity is not None:
                expected += Decimal(str(batch_item.expected_quantity))
            else:
                expected += Decimal(str(formula_row.quantity or 0))
            if batch_item is not None and batch_item.actual_quantity is not None:
                actual += Decimal(str(batch_item.actual_quantity))
                any_actual = True
        return (expected if expected > 0 else None), (actual if any_actual else None)

    outputs = [row for row in batch_items if row.item_role == "output"]
    if not outputs:
        return None, None
    expected = sum((Decimal(str(row.expected_quantity or 0)) for row in outputs), Decimal("0"))
    actuals = [row.actual_quantity for row in outputs if row.actual_quantity is not None]
    actual = sum((Decimal(str(value)) for value in actuals), Decimal("0")) if actuals else None
    return (expected if expected > 0 else None), actual


def _elapsed_minutes(logs: Sequence[Any], now: datetime) -> Optional[int]:
    total = 0
    any_span = False
    for log in logs:
        started = getattr(log, "started_at", None)
        if started is None:
            continue
        ended = getattr(log, "completed_at", None)
        if ended is None and getattr(log, "status", None) == "in_progress":
            ended = now
        minutes = duration_minutes(started, ended)
        if minutes is None:
            continue
        total += minutes
        any_span = True
    return total if any_span else None


def _planned_minutes(logs: Sequence[Any]) -> Optional[int]:
    total = 0
    any_minutes = False
    for log in logs:
        minutes = getattr(log, "expected_duration_minutes", None)
        if minutes is None:
            continue
        total += int(minutes)
        any_minutes = True
    return total if any_minutes else None


def derive_batch_totals(
    *,
    logs: Sequence[Any],
    batch_items: Sequence[Any],
    formula_stage_items: Sequence[Any] = (),
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    """Expected qty follows the last step's output lines. Minutes are elapsed step time."""
    clock = now or utcnow()
    last = _last_log(logs)
    expected_out = None
    actual_out = None
    if last is not None:
        expected_out, actual_out = _output_quantities(last, batch_items, formula_stage_items)

    variance_qty = None
    variance_pct = None
    efficiency = None
    if actual_out is not None and expected_out is not None and expected_out > 0:
        variance_qty = actual_out - expected_out
        variance_pct = Decimal(str(round((variance_qty / expected_out) * 100, 2)))
        efficiency = Decimal(str(round((actual_out / expected_out) * 100, 2)))

    return {
        "expected_output_quantity": expected_out,
        "actual_output_quantity": actual_out,
        "expected_duration_minutes": _planned_minutes(logs),
        "actual_duration_minutes": _elapsed_minutes(logs, clock),
        "output_variance_quantity": variance_qty,
        "output_variance_percentage": variance_pct,
        "efficiency_percentage": efficiency,
    }


def apply_batch_totals(batch: Any, totals: dict[str, Any]) -> Any:
    for key, value in totals.items():
        setattr(batch, key, value)
    return batch
