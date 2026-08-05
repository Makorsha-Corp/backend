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


def utcnow() -> datetime:
    """Current UTC time as a naive datetime (tzinfo stripped)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
