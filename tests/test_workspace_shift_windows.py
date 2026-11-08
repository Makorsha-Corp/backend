from datetime import datetime, time, timezone
from types import SimpleNamespace

import pytest

from app.utils.workspace_shift_windows import (
    assert_no_overlap_with_siblings,
    find_shift_for_local_datetime,
    minutes_in_window,
    wall_clock_for_shift,
    windows_overlap_minutes,
)


def test_overnight_window():
    assert minutes_in_window(23 * 60, 22 * 60, 6 * 60)
    assert minutes_in_window(3 * 60, 22 * 60, 6 * 60)
    assert not minutes_in_window(12 * 60, 22 * 60, 6 * 60)


def test_overlap_rejects():
    a = SimpleNamespace(id=1, name="A", start_time=time(6, 0), end_time=time(14, 0), sort_order=0, is_active=True)
    with pytest.raises(ValueError, match="overlap"):
        assert_no_overlap_with_siblings(time(10, 0), time(18, 0), [a])


def test_find_shift_overnight():
    night = SimpleNamespace(
        id=2, name="Night", start_time=time(22, 0), end_time=time(6, 0), sort_order=1, is_active=True
    )
    morning = SimpleNamespace(
        id=1, name="Morning", start_time=time(6, 0), end_time=time(14, 0), sort_order=0, is_active=True
    )
    found = find_shift_for_local_datetime(datetime(2026, 3, 1, 23, 30), [morning, night])
    assert found.name == "Night"


def test_wall_clock_converts_utc_instant_to_dhaka():
    # 00:00 UTC is 06:00 in Asia/Dhaka. Morning is 06:00–14:00.
    morning = SimpleNamespace(
        id=1, name="Morning", start_time=time(6, 0), end_time=time(14, 0), sort_order=0, is_active=True
    )
    instant = datetime(2026, 10, 20, 0, 0, tzinfo=timezone.utc)
    wall = wall_clock_for_shift(instant, "Asia/Dhaka")
    assert wall.hour == 6
    assert wall.day == 20
    assert find_shift_for_local_datetime(wall, [morning]).name == "Morning"
    assert find_shift_for_local_datetime(instant, [morning]) is None


def test_windows_overlap_minutes():
    assert windows_overlap_minutes(6 * 60, 14 * 60, 10 * 60, 18 * 60)
    assert not windows_overlap_minutes(6 * 60, 14 * 60, 14 * 60, 22 * 60)
