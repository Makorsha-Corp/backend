"""Tests for work order calendar date helper."""

from datetime import date, datetime, timezone

from app.utils.work_order_calendar import work_order_calendar_date


def test_calendar_date_uses_planned_date_when_set() -> None:
    created = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)
    assert work_order_calendar_date(planned_date=date(2026, 7, 26), created_at=created) == date(2026, 7, 26)


def test_calendar_date_falls_back_to_created_at_day() -> None:
    created = datetime(2026, 7, 23, 0, 29, tzinfo=timezone.utc)
    assert work_order_calendar_date(planned_date=None, created_at=created) == date(2026, 7, 23)
