"""Tests for production overview stats aggregation."""
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from app.utils.production_batch_overview_stats import build_overview_stats
from app.utils.time import reject_future_started_at, utcnow


class _Batch:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class _Log:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class _Param:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def test_build_overview_stats_yield_and_outlier():
    batch = _Batch(
        id=1,
        batch_number="B-1",
        production_line_id=10,
        formula_id=5,
        status="completed",
        expected_output_quantity=1000,
        efficiency_percentage=Decimal("84"),
        expected_duration_minutes=120,
        actual_duration_minutes=130,
        started_at=datetime(2026, 1, 1, 8, 0),
        actual_start_time=None,
        actual_end_time=None,
        planned_start_at=datetime(2026, 1, 1, 7, 45),
    )
    batch2 = _Batch(
        id=2,
        batch_number="B-2",
        production_line_id=10,
        formula_id=5,
        status="completed",
        expected_output_quantity=1000,
        efficiency_percentage=Decimal("105"),
        expected_duration_minutes=120,
        actual_duration_minutes=115,
        started_at=datetime(2026, 1, 2, 8, 0),
        actual_start_time=None,
        actual_end_time=None,
        planned_start_at=None,
    )
    result = build_overview_stats(
        batches=[batch, batch2],
        logs_by_batch={},
        params_by_log={},
        line_names={10: "Line A"},
        formula_names={5: "Yarn"},
        date_from=date(2026, 1, 1),
        date_to=date(2026, 1, 31),
    )
    assert len(result["lines"]) == 1
    line = result["lines"][0]
    assert line["line_name"] == "Line A"
    assert line["yield_pct"] is not None
    assert line["recipes"][0]["recipe_name"] == "Yarn"
    assert any(o["metric"] == "yield" for o in result["outliers"])
    assert line["batch_count"] == 2
    assert line["recipes"][0]["batch_count"] == 2


def test_build_overview_stats_output_and_waste():
    batch = _Batch(
        id=1,
        batch_number="B-1",
        production_line_id=10,
        formula_id=5,
        status="completed",
        expected_output_quantity=100,
        actual_output_quantity=95,
        efficiency_percentage=Decimal("95"),
        expected_duration_minutes=60,
        actual_duration_minutes=60,
        started_at=None,
        actual_start_time=None,
        actual_end_time=None,
        planned_start_at=None,
    )

    class _Item:
        item_role = "waste"
        actual_quantity = 3

    result = build_overview_stats(
        batches=[batch],
        logs_by_batch={},
        params_by_log={},
        items_by_batch={1: [_Item()]},
        line_names={10: "Line A"},
        formula_names={5: "Yarn"},
        date_from=date(2026, 1, 1),
        date_to=date(2026, 1, 31),
    )
    line = result["lines"][0]
    assert line["batch_count"] == 1
    assert line["output_quantity"] == 95
    assert line["waste_quantity"] == 3


def test_reject_future_started_at():
    reject_future_started_at(None)
    past = utcnow() - timedelta(hours=1)
    reject_future_started_at(past)
    future = utcnow() + timedelta(hours=1)
    with pytest.raises(ValueError, match="future"):
        reject_future_started_at(future)
