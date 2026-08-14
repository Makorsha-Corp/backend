"""Tests for UTC datetime JSON serialization."""
from datetime import datetime, timezone

from app.utils.datetime_serialize import ensure_utc_z_in_json, serialize_utc_datetime


def test_serialize_utc_datetime_naive():
    dt = datetime(2026, 8, 10, 23, 54, 0)
    assert serialize_utc_datetime(dt) == "2026-08-10T23:54:00Z"


def test_serialize_utc_datetime_aware():
    dt = datetime(2026, 8, 10, 23, 54, 0, tzinfo=timezone.utc)
    assert serialize_utc_datetime(dt) == "2026-08-10T23:54:00Z"


def test_ensure_utc_z_in_json_appends_z_to_naive_iso():
    payload = {
        "created_at": "2026-08-10T23:54:00",
        "planned_date": "2026-08-11",
        "nested": [{"at": "2026-08-10T18:18:00.123456"}],
    }
    fixed = ensure_utc_z_in_json(payload)
    assert fixed["created_at"] == "2026-08-10T23:54:00Z"
    assert fixed["planned_date"] == "2026-08-11"
    assert fixed["nested"][0]["at"] == "2026-08-10T18:18:00.123456Z"


def test_ensure_utc_z_leaves_existing_z():
    payload = {"created_at": "2026-08-10T23:54:00Z"}
    assert ensure_utc_z_in_json(payload)["created_at"] == "2026-08-10T23:54:00Z"
