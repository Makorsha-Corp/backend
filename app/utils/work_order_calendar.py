"""Calendar date helpers for work orders (planned_date or created_at day)."""
from datetime import date, datetime


def work_order_calendar_date(*, planned_date: date | None, created_at: datetime) -> date:
    """Day used for sheet grouping, filters, and calendar dots."""
    if planned_date is not None:
        return planned_date
    return created_at.date()
