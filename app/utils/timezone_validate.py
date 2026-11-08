"""IANA timezone validation helpers."""
from __future__ import annotations

import tzdata  # noqa: F401  — Windows has no system zoneinfo; ZoneInfo reads this package.
from zoneinfo import ZoneInfo


def is_valid_iana_timezone(value: str) -> bool:
    if not value or len(value) > 64:
        return False
    try:
        ZoneInfo(value)
    except Exception:
        return False
    return True
