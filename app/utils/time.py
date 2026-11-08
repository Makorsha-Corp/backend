"""
Time helpers.

The database stores TIMESTAMP WITHOUT TIME ZONE and the whole codebase
treats those values as UTC. `utcnow()` preserves that contract (naive UTC)
while using the non-deprecated API — `datetime.utcnow()` is deprecated since
Python 3.12.

If the schema ever migrates to timestamptz columns, change this helper to
return `datetime.now(timezone.utc)` and audit comparisons against DB values.
"""
from datetime import datetime, timezone
from typing import Optional


def utcnow() -> datetime:
    """Current UTC time as a naive datetime (tzinfo stripped)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def utcnow_aware() -> datetime:
    """Current UTC time with tzinfo (for timestamptz columns)."""
    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    """UTC-aware datetime. Naive values are UTC, matching TIMESTAMP WITHOUT TIME ZONE."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def reject_future_started_at(started_at: Optional[datetime]) -> None:
    """Raise ValueError if started_at is after current UTC time."""
    if started_at is None:
        return
    if started_at > utcnow():
        raise ValueError("started_at cannot be in the future")
