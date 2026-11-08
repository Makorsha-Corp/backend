from datetime import date

import pytest

from app.utils.work_order_recurrence import list_recurrence_planned_dates


def test_weekly_planned_dates():
    dates = list_recurrence_planned_dates(
        date(2026, 10, 5), date(2026, 10, 19), "weekly"
    )
    assert dates == [date(2026, 10, 5), date(2026, 10, 12), date(2026, 10, 19)]


def test_custom_every_n_days():
    dates = list_recurrence_planned_dates(
        date(2026, 10, 1), date(2026, 10, 10), "custom", interval_days=3
    )
    assert dates == [
        date(2026, 10, 1),
        date(2026, 10, 4),
        date(2026, 10, 7),
        date(2026, 10, 10),
    ]


def test_span_over_max_rejected():
    with pytest.raises(ValueError, match="183"):
        list_recurrence_planned_dates(
            date(2026, 1, 1), date(2026, 12, 31), "daily"
        )
