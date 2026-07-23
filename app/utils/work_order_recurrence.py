"""Recurrence helpers for work order templates."""
from __future__ import annotations

import calendar
from datetime import date, timedelta
from typing import Literal, Optional

WorkOrderGenerationMode = Literal['schedule', 'draft']


def advance_next_generation_date(
    *,
    from_date: date,
    recurrence_type: Optional[str],
    recurrence_day: Optional[int],
) -> date:
    """Compute the next generation date after a successful run on from_date."""
    if recurrence_type == 'daily':
        return from_date + timedelta(days=1)

    if recurrence_type == 'weekly':
        if recurrence_day is None:
            return from_date + timedelta(days=7)
        target_dow = recurrence_day % 7
        days_ahead = (target_dow - from_date.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        return from_date + timedelta(days=days_ahead)

    if recurrence_type == 'monthly':
        day = recurrence_day if recurrence_day is not None else from_date.day
        day = max(1, min(day, 31))
        if from_date.month == 12:
            year, month = from_date.year + 1, 1
        else:
            year, month = from_date.year, from_date.month + 1
        last_day = calendar.monthrange(year, month)[1]
        return date(year, month, min(day, last_day))

    return from_date + timedelta(days=1)


def should_advance_template(template, target_date: date) -> bool:
    return (
        template.is_recurring
        and template.next_generation_date is not None
        and template.next_generation_date <= target_date
    )
