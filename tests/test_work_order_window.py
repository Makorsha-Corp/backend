from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

import pytest

from app.utils.work_order_window import (
    move_window_to_date,
    resolve_work_order_window,
    untimed_day_bounds,
    windows_intersect,
)


DHAKA = ZoneInfo("Asia/Dhaka")


def utc(y, m, d, hh, mm):
    return datetime(y, m, d, hh, mm, tzinfo=DHAKA).astimezone(timezone.utc)


def test_date_only_is_untimed():
    assert resolve_work_order_window(
        planned_date=date(2026, 11, 2),
        planned_start_time=None,
        expected_duration_minutes=None,
        tz_name="Asia/Dhaka",
    ) == (None, None)


def test_clock_without_duration_ends_at_end_of_day():
    start, end = resolve_work_order_window(
        planned_date=date(2026, 11, 2),
        planned_start_time=time(12, 0),
        expected_duration_minutes=None,
        tz_name="Asia/Dhaka",
    )
    assert start == utc(2026, 11, 2, 12, 0)
    assert end == utc(2026, 11, 3, 0, 0)


def test_clock_plus_duration():
    start, end = resolve_work_order_window(
        planned_date=date(2026, 11, 2),
        planned_start_time=time(6, 30),
        expected_duration_minutes=120,
        tz_name="Asia/Dhaka",
    )
    assert start == utc(2026, 11, 2, 6, 30)
    assert end == utc(2026, 11, 2, 8, 30)


def test_duration_past_midnight_is_kept():
    start, end = resolve_work_order_window(
        planned_date=date(2026, 11, 2),
        planned_start_time=time(22, 0),
        expected_duration_minutes=180,
        tz_name="Asia/Dhaka",
    )
    assert start == utc(2026, 11, 2, 22, 0)
    assert end == utc(2026, 11, 3, 1, 0)


def test_duration_without_clock_raises():
    with pytest.raises(ValueError, match="Duration requires a start time"):
        resolve_work_order_window(
            planned_date=date(2026, 11, 2),
            planned_start_time=None,
            expected_duration_minutes=30,
            tz_name="Asia/Dhaka",
        )


def test_move_window_keeps_local_start_and_length():
    start, end = resolve_work_order_window(
        planned_date=date(2026, 11, 2),
        planned_start_time=time(23, 0),
        expected_duration_minutes=180,
        tz_name="Asia/Dhaka",
    )
    moved_start, moved_end = move_window_to_date(start, end, date(2026, 11, 5), "Asia/Dhaka")
    assert moved_start == utc(2026, 11, 5, 23, 0)
    assert moved_end - moved_start == end - start


def test_windows_intersect_is_half_open():
    a0, a1 = utc(2026, 11, 2, 6, 0), utc(2026, 11, 2, 8, 0)
    b0, b1 = utc(2026, 11, 2, 8, 0), utc(2026, 11, 2, 10, 0)
    assert windows_intersect(a0, a1, b0, b1) is False
    assert windows_intersect(a0, a1, utc(2026, 11, 2, 7, 0), utc(2026, 11, 2, 9, 0)) is True


def test_untimed_day_bounds():
    start, end = untimed_day_bounds(date(2026, 11, 2), "Asia/Dhaka")
    assert start == utc(2026, 11, 2, 0, 0)
    assert end == utc(2026, 11, 3, 0, 0)
