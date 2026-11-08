"""Recurrence helpers for work order templates."""
from __future__ import annotations

import calendar
from datetime import date, timedelta
from typing import Literal, Optional

WorkOrderGenerationMode = Literal['schedule', 'draft']

RECURRENCE_MAX_SPAN_DAYS = 183  # ~6 months
MAX_PROGRAM_OCCURRENCES = 366


def list_recurrence_planned_dates(
    start_date: date,
    end_date: date,
    recurrence_type: str | None,
    interval_days: int | None = None,
) -> list[date]:
    """All planned dates from start through end inclusive."""
    validate_recurrence_span(start_date, end_date)
    cadence = recurrence_type or "weekly"
    if cadence not in {"daily", "weekly", "monthly", "custom"}:
        raise ValueError("Cadence must be daily, weekly, monthly, or custom")
    if cadence == "custom":
        step = interval_days or 0
        if step < 1:
            raise ValueError("Custom cadence requires interval_days of at least 1")
        dates: list[date] = [start_date]
        cursor = start_date
        while cursor < end_date:
            cursor = cursor + timedelta(days=step)
            if cursor > end_date:
                break
            dates.append(cursor)
            if len(dates) > MAX_PROGRAM_OCCURRENCES:
                raise ValueError(
                    f"Recurrence cannot exceed {MAX_PROGRAM_OCCURRENCES} occurrences"
                )
        return dates

    recurrence_day = start_date.day if cadence == "monthly" else None
    dates = [start_date]
    cursor = start_date
    while cursor < end_date:
        cursor = advance_next_generation_date(
            from_date=cursor,
            recurrence_type=cadence,
            recurrence_day=recurrence_day,
        )
        if cursor > end_date:
            break
        dates.append(cursor)
        if len(dates) > MAX_PROGRAM_OCCURRENCES:
            raise ValueError(
                f"Recurrence cannot exceed {MAX_PROGRAM_OCCURRENCES} occurrences"
            )
    return dates


def validate_recurrence_span(start_date: date, end_date: date) -> None:
    """Raise ValueError when end is before start or span exceeds max."""
    if end_date < start_date:
        raise ValueError('Recurrence end date must be on or after the start date')
    if (end_date - start_date).days > RECURRENCE_MAX_SPAN_DAYS:
        raise ValueError(f'Recurrence range cannot exceed {RECURRENCE_MAX_SPAN_DAYS} days (~6 months)')


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


def _apply_recurrence_range(
    template,
    planned_date: date,
    recurrence_end_date: date,
) -> None:
    validate_recurrence_span(planned_date, recurrence_end_date)
    template.recurrence_start_date = planned_date
    template.recurrence_end_date = recurrence_end_date
    if template.recurrence_type == 'monthly':
        template.recurrence_day = planned_date.day
    else:
        template.recurrence_day = None
    template.next_generation_date = advance_next_generation_date(
        from_date=planned_date,
        recurrence_type=template.recurrence_type,
        recurrence_day=template.recurrence_day,
    )


def seed_recurrence_from_planned_date(
    template,
    planned_date: date,
    recurrence_end_date: date,
) -> None:
    """First sheet placement anchors recurring template schedule."""
    if not template.is_recurring or template.next_generation_date is not None:
        return
    _apply_recurrence_range(template, planned_date, recurrence_end_date)


def reseed_recurrence_program(
    template,
    planned_date: date,
    recurrence_end_date: date,
) -> None:
    """Overwrite recurring template schedule when user repicks range on sheet."""
    if not template.is_recurring:
        return
    _apply_recurrence_range(template, planned_date, recurrence_end_date)


def is_recurrence_program_active(template, target_date: date) -> bool:
    """True when Plan day may still generate for this template on target_date."""
    if not template.is_recurring or template.next_generation_date is None:
        return False
    if template.recurrence_end_date is not None and target_date > template.recurrence_end_date:
        return False
    return True


def should_advance_template(template, target_date: date) -> bool:
    return (
        template.is_recurring
        and template.next_generation_date is not None
        and template.next_generation_date <= target_date
        and is_recurrence_program_active(template, target_date)
    )
