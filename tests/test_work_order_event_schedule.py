"""Unit tests for work order schedule metadata on lifecycle events."""
from datetime import date, datetime

from app.managers.work_order_manager import work_order_manager


def test_variance_vs_planned_on_time() -> None:
    result = work_order_manager._variance_vs_planned(
        date(2026, 7, 23),
        datetime(2026, 7, 23, 14, 30),
    )
    assert result is not None
    assert result['variance_days'] == 0
    assert result['variance_label'] == 'On plan'


def test_variance_vs_planned_early() -> None:
    result = work_order_manager._variance_vs_planned(
        date(2026, 7, 23),
        datetime(2026, 7, 21, 9, 0),
    )
    assert result is not None
    assert result['variance_days'] == -2
    assert result['variance_label'] == '2 days early'


def test_variance_vs_planned_late() -> None:
    result = work_order_manager._variance_vs_planned(
        date(2026, 7, 23),
        datetime(2026, 7, 25, 17, 0),
    )
    assert result is not None
    assert result['variance_days'] == 2
    assert result['variance_label'] == '2 days late'
