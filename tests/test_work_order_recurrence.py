"""Tests for work order template recurrence date advancement."""

from datetime import date

from app.utils.work_order_recurrence import advance_next_generation_date


def test_advance_daily() -> None:
    assert advance_next_generation_date(
        from_date=date(2026, 7, 23),
        recurrence_type='daily',
        recurrence_day=None,
    ) == date(2026, 7, 24)


def test_advance_weekly_default_seven_days() -> None:
    assert advance_next_generation_date(
        from_date=date(2026, 7, 23),
        recurrence_type='weekly',
        recurrence_day=None,
    ) == date(2026, 7, 30)


def test_advance_weekly_with_recurrence_day() -> None:
    # 2026-07-23 is Thursday (weekday 3); next Monday (0) is 2026-07-27
    assert advance_next_generation_date(
        from_date=date(2026, 7, 23),
        recurrence_type='weekly',
        recurrence_day=0,
    ) == date(2026, 7, 27)


def test_advance_monthly_respects_day_of_month() -> None:
    assert advance_next_generation_date(
        from_date=date(2026, 7, 15),
        recurrence_type='monthly',
        recurrence_day=15,
    ) == date(2026, 8, 15)


def test_advance_monthly_clamps_to_month_end() -> None:
    assert advance_next_generation_date(
        from_date=date(2026, 1, 31),
        recurrence_type='monthly',
        recurrence_day=31,
    ) == date(2026, 2, 28)
