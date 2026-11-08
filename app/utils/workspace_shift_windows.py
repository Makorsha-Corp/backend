"""Match datetimes to workspace shift windows and detect overlaps."""
from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from typing import Iterable, Optional, Protocol, Sequence
from zoneinfo import ZoneInfo

DEFAULT_MILL_TIMEZONE = "Asia/Dhaka"


class ShiftWindowLike(Protocol):
    id: int
    name: str
    start_time: time
    end_time: time
    sort_order: int
    is_active: bool


def time_to_minutes(t: time) -> int:
    return t.hour * 60 + t.minute


def minutes_in_window(minute: int, start: int, end: int) -> bool:
    """Minute-of-day in [start, end) with overnight when end <= start."""
    minute = minute % 1440
    if start == end:
        return False
    if start < end:
        return start <= minute < end
    return minute >= start or minute < end


def windows_overlap_minutes(start_a: int, end_a: int, start_b: int, end_b: int) -> bool:
    """True if the two windows share any minute-of-day."""
    for probe in range(1440):
        if minutes_in_window(probe, start_a, end_a) and minutes_in_window(probe, start_b, end_b):
            return True
    return False


def assert_no_overlap_with_siblings(
    start: time,
    end: time,
    siblings: Sequence[ShiftWindowLike],
    *,
    exclude_id: Optional[int] = None,
) -> None:
    s = time_to_minutes(start)
    e = time_to_minutes(end)
    for row in siblings:
        if not row.is_active:
            continue
        if exclude_id is not None and row.id == exclude_id:
            continue
        if windows_overlap_minutes(s, e, time_to_minutes(row.start_time), time_to_minutes(row.end_time)):
            raise ValueError(f"Shift window overlaps with '{row.name}'")


def wall_clock_for_shift(when: datetime, tz_name: str | None = None) -> datetime:
    """Shift windows are mill wall-clock. Naive values are UTC, matching API JSON."""
    name = (tz_name or "").strip() or DEFAULT_MILL_TIMEZONE
    try:
        tz = ZoneInfo(name)
    except Exception:
        tz = ZoneInfo(DEFAULT_MILL_TIMEZONE)
    aware = when if when.tzinfo is not None else when.replace(tzinfo=timezone.utc)
    local = aware.astimezone(tz)
    return local.replace(tzinfo=None)


def find_shift_for_local_datetime(
    when: datetime,
    shifts: Iterable[ShiftWindowLike],
) -> Optional[ShiftWindowLike]:
    """Pick active shift containing when's local time-of-day; lowest sort_order wins ties."""
    minute = when.hour * 60 + when.minute
    matches: list[ShiftWindowLike] = []
    for row in shifts:
        if not row.is_active:
            continue
        s = time_to_minutes(row.start_time)
        e = time_to_minutes(row.end_time)
        if minutes_in_window(minute, s, e):
            matches.append(row)
    if not matches:
        return None
    return sorted(matches, key=lambda r: (r.sort_order, r.id))[0]


def shift_window_start_on_date(shift: ShiftWindowLike, on_date: datetime) -> datetime:
    """Local datetime at shift start on the calendar day of on_date."""
    base = on_date.replace(hour=shift.start_time.hour, minute=shift.start_time.minute, second=0, microsecond=0)
    return base


def now_or_window_start(shift: ShiftWindowLike, reference: datetime, *, now: datetime) -> datetime:
    """If now falls in shift window on reference's date, return now; else shift start that day."""
    ref_day = reference.replace(hour=now.hour, minute=now.minute, second=now.second, microsecond=now.microsecond)
    minute = time_to_minutes(now.time())
    s = time_to_minutes(shift.start_time)
    e = time_to_minutes(shift.end_time)
    if minutes_in_window(minute, s, e):
        return now.replace(microsecond=0)
    return shift_window_start_on_date(shift, reference)
