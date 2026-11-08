"""Resolve a work-order shift window into UTC instants."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Protocol
from zoneinfo import ZoneInfo

from app.utils.workspace_shift_windows import DEFAULT_MILL_TIMEZONE


class WindowShift(Protocol):
    start_time: time
    end_time: time


def _zone(tz_name: str | None) -> ZoneInfo:
    name = (tz_name or "").strip() or DEFAULT_MILL_TIMEZONE
    try:
        return ZoneInfo(name)
    except Exception:
        return ZoneInfo(DEFAULT_MILL_TIMEZONE)


def _to_utc(local: datetime, tz: ZoneInfo) -> datetime:
    return local.replace(tzinfo=tz).astimezone(timezone.utc)


def resolve_work_order_window(
    *,
    planned_date: date | None,
    shift: WindowShift | None = None,
    planned_start_time: time | None,
    expected_duration_minutes: int | None,
    tz_name: str | None,
) -> tuple[datetime | None, datetime | None]:
    del shift  # legacy callers; timing no longer depends on workspace shifts
    if planned_date is None:
        return None, None
    if expected_duration_minutes is not None and planned_start_time is None:
        raise ValueError("Duration requires a start time")
    if planned_start_time is None:
        return None, None

    tz = _zone(tz_name)
    start_local = datetime(
        planned_date.year,
        planned_date.month,
        planned_date.day,
        planned_start_time.hour,
        planned_start_time.minute,
    )
    start = _to_utc(start_local, tz)
    if expected_duration_minutes is not None:
        return start, start + timedelta(minutes=expected_duration_minutes)
    _day_start, day_end = untimed_day_bounds(planned_date, tz_name)
    return start, day_end


def move_window_to_date(
    start: datetime,
    end: datetime,
    new_date: date,
    tz_name: str | None,
) -> tuple[datetime, datetime]:
    tz = _zone(tz_name)
    local_start = start.astimezone(tz)
    length = end - start
    moved = datetime(new_date.year, new_date.month, new_date.day, local_start.hour, local_start.minute, tzinfo=tz)
    return moved.astimezone(timezone.utc), (moved + length).astimezone(timezone.utc)


def untimed_day_bounds(planned_date: date, tz_name: str | None) -> tuple[datetime, datetime]:
    tz = _zone(tz_name)
    start = datetime(planned_date.year, planned_date.month, planned_date.day, tzinfo=tz)
    return start.astimezone(timezone.utc), (start + timedelta(days=1)).astimezone(timezone.utc)


def windows_intersect(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    return a_start < b_end and b_start < a_end
