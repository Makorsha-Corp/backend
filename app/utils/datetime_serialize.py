"""Serialize datetimes for API JSON — always UTC with Z suffix."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

# Naive ISO datetime from Pydantic (no timezone suffix).
_NAIVE_ISO_DATETIME = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?$"
)


def serialize_utc_datetime(dt: datetime) -> str:
    """Format a datetime as ISO-8601 UTC with trailing Z."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)

    text = dt.strftime("%Y-%m-%dT%H:%M:%S")
    if dt.microsecond:
        micro = f"{dt.microsecond:06d}".rstrip("0")
        text = f"{text}.{micro}"
    return f"{text}Z"


def ensure_utc_z_in_json(value: Any) -> Any:
    """Walk JSON-serializable structures and append Z to naive ISO datetimes."""
    if isinstance(value, dict):
        return {key: ensure_utc_z_in_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [ensure_utc_z_in_json(item) for item in value]
    if isinstance(value, str) and _NAIVE_ISO_DATETIME.match(value):
        return f"{value}Z"
    return value
