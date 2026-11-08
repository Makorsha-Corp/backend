"""Start datetimes for a production recurring program."""
from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta

from app.utils.workspace_shift_windows import wall_clock_for_shift

MAX_PROGRAM_OCCURRENCES = 366


def _add_month(value: datetime, anchor_day: int) -> datetime:
    year = value.year + (1 if value.month == 12 else 0)
    month = 1 if value.month == 12 else value.month + 1
    last_day = calendar.monthrange(year, month)[1]
    return value.replace(year=year, month=month, day=min(anchor_day, last_day))


def occurrence_starts(
    first_start: datetime,
    cadence: str,
    end_date: date,
    tz_name: str | None = None,
    interval_days: int | None = None,
) -> list[datetime]:
    """Include a start while its mill wall-clock date is on or before end_date.

    The returned instants are the inputs stepped by cadence. Naive datetimes are UTC.
    A missing timezone uses the mill default inside wall_clock_for_shift.
    """
    if end_date < wall_clock_for_shift(first_start, tz_name).date():
        raise ValueError("Recurrence end date must be on or after the start date")
    if cadence not in {"daily", "weekly", "monthly", "custom"}:
        raise ValueError("Cadence must be daily, weekly, monthly, or custom")
    if cadence == "custom":
        step = interval_days or 0
        if step < 1:
            raise ValueError("Custom cadence requires interval_days of at least 1")

    starts: list[datetime] = []
    cursor = first_start
    while wall_clock_for_shift(cursor, tz_name).date() <= end_date:
        starts.append(cursor)
        if len(starts) > MAX_PROGRAM_OCCURRENCES:
            raise ValueError(
                f"Recurrence cannot exceed {MAX_PROGRAM_OCCURRENCES} occurrences"
            )
        if cadence == "daily":
            cursor = cursor + timedelta(days=1)
        elif cadence == "weekly":
            cursor = cursor + timedelta(days=7)
        elif cadence == "custom":
            cursor = cursor + timedelta(days=step)
        else:
            cursor = _add_month(cursor, first_start.day)
    return starts
