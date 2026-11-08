"""Derived batch header totals."""
from datetime import datetime

from app.utils.batch_derived_totals import derive_batch_totals


class _Row:
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


def test_expected_follows_last_step_output_not_earlier_steps():
    logs = [
        _Row(id=1, stage_order=0, formula_stage_id=10, status="completed", expected_duration_minutes=15),
        _Row(id=2, stage_order=1, formula_stage_id=11, status="in_progress", expected_duration_minutes=20),
    ]
    items = [
        _Row(item_id=1, item_role="output", expected_quantity=8, actual_quantity=7),
        _Row(item_id=2, item_role="output", expected_quantity=3, actual_quantity=None),
    ]
    formula_items = [
        _Row(formula_stage_id=10, item_id=1, item_role="output", quantity=8),
        _Row(formula_stage_id=11, item_id=2, item_role="output", quantity=2),
    ]
    totals = derive_batch_totals(logs=logs, batch_items=items, formula_stage_items=formula_items)
    assert totals["expected_output_quantity"] == 3
    assert totals["actual_output_quantity"] is None
    assert totals["expected_duration_minutes"] == 35


def test_actual_and_elapsed_minutes():
    logs = [
        _Row(
            id=1,
            stage_order=0,
            formula_stage_id=10,
            status="completed",
            expected_duration_minutes=10,
            started_at=datetime(2026, 10, 5, 6, 0),
            completed_at=datetime(2026, 10, 5, 6, 40),
        ),
    ]
    items = [
        _Row(item_id=1, item_role="output", expected_quantity=5, actual_quantity=4),
    ]
    formula_items = [
        _Row(formula_stage_id=10, item_id=1, item_role="output", quantity=5),
    ]
    totals = derive_batch_totals(logs=logs, batch_items=items, formula_stage_items=formula_items)
    assert totals["actual_output_quantity"] == 4
    assert totals["actual_duration_minutes"] == 40
    assert totals["output_variance_quantity"] == -1
    assert float(totals["efficiency_percentage"]) == 80.0


def test_no_steps_leaves_totals_empty():
    totals = derive_batch_totals(logs=[], batch_items=[])
    assert totals["expected_output_quantity"] is None
    assert totals["actual_duration_minutes"] is None
