"""Tests for work order template recurrence date advancement."""

from datetime import date
from types import SimpleNamespace

import pytest

from app.utils.work_order_recurrence import (
    RECURRENCE_MAX_SPAN_DAYS,
    advance_next_generation_date,
    reseed_recurrence_program,
    seed_recurrence_from_planned_date,
    validate_recurrence_span,
)


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


def test_validate_recurrence_span_rejects_end_before_start() -> None:
    with pytest.raises(ValueError, match='on or after'):
        validate_recurrence_span(date(2026, 3, 1), date(2026, 2, 1))


def test_validate_recurrence_span_rejects_over_six_months() -> None:
    with pytest.raises(ValueError, match=str(RECURRENCE_MAX_SPAN_DAYS)):
        validate_recurrence_span(date(2026, 1, 1), date(2026, 8, 1))


def test_seed_recurrence_from_planned_date_weekly() -> None:
    tpl = SimpleNamespace(
        is_recurring=True,
        next_generation_date=None,
        recurrence_type='weekly',
        recurrence_day=None,
        recurrence_start_date=None,
        recurrence_end_date=None,
    )
    seed_recurrence_from_planned_date(tpl, date(2026, 1, 15), date(2026, 3, 15))
    assert tpl.recurrence_start_date == date(2026, 1, 15)
    assert tpl.recurrence_end_date == date(2026, 3, 15)
    assert tpl.recurrence_day is None
    assert tpl.next_generation_date == date(2026, 1, 22)


def test_seed_recurrence_from_planned_date_monthly_sets_day() -> None:
    tpl = SimpleNamespace(
        is_recurring=True,
        next_generation_date=None,
        recurrence_type='monthly',
        recurrence_day=None,
        recurrence_start_date=None,
        recurrence_end_date=None,
    )
    seed_recurrence_from_planned_date(tpl, date(2026, 1, 15), date(2026, 4, 15))
    assert tpl.recurrence_day == 15
    assert tpl.next_generation_date == date(2026, 2, 15)


def test_seed_recurrence_skips_when_already_anchored() -> None:
    tpl = SimpleNamespace(
        is_recurring=True,
        next_generation_date=date(2026, 2, 1),
        recurrence_type='weekly',
        recurrence_day=None,
        recurrence_start_date=date(2026, 1, 1),
        recurrence_end_date=date(2026, 6, 1),
    )
    seed_recurrence_from_planned_date(tpl, date(2026, 1, 15), date(2026, 3, 15))
    assert tpl.recurrence_start_date == date(2026, 1, 1)
    assert tpl.next_generation_date == date(2026, 2, 1)


def test_reseed_recurrence_program_overwrites_when_anchored() -> None:
    tpl = SimpleNamespace(
        is_recurring=True,
        next_generation_date=date(2026, 2, 1),
        recurrence_type='weekly',
        recurrence_day=None,
        recurrence_start_date=date(2026, 1, 1),
        recurrence_end_date=date(2026, 6, 1),
    )
    reseed_recurrence_program(tpl, date(2026, 3, 1), date(2026, 5, 1))
    assert tpl.recurrence_start_date == date(2026, 3, 1)
    assert tpl.recurrence_end_date == date(2026, 5, 1)
    assert tpl.next_generation_date == date(2026, 3, 8)
