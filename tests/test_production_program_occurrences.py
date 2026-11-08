from datetime import date, datetime, timezone

import pytest

from app.utils.production_program_occurrences import (
    MAX_PROGRAM_OCCURRENCES,
    occurrence_starts,
)


def test_weekly_stops_on_end_date():
    starts = occurrence_starts(
        datetime(2026, 10, 5, 6, 0),
        "weekly",
        date(2026, 10, 20),
    )
    assert starts == [
        datetime(2026, 10, 5, 6, 0),
        datetime(2026, 10, 12, 6, 0),
        datetime(2026, 10, 19, 6, 0),
    ]


def test_monthly_clamps_to_last_day():
    starts = occurrence_starts(
        datetime(2026, 1, 31, 8, 30),
        "monthly",
        date(2026, 3, 31),
    )
    assert [row.date() for row in starts] == [
        date(2026, 1, 31),
        date(2026, 2, 28),
        date(2026, 3, 31),
    ]
    assert all(row.hour == 8 and row.minute == 30 for row in starts)


def test_daily_end_date_uses_mill_wall_clock():
    first = datetime(2026, 10, 24, 19, 0, tzinfo=timezone.utc)
    starts = occurrence_starts(first, "daily", date(2026, 10, 25), "Asia/Dhaka")
    assert starts == [first]


def test_end_before_start_raises():
    with pytest.raises(ValueError, match="on or after"):
        occurrence_starts(datetime(2026, 10, 5, 6, 0), "daily", date(2026, 10, 4))


def test_over_366_raises_and_names_the_cap():
    with pytest.raises(ValueError, match=str(MAX_PROGRAM_OCCURRENCES)):
        occurrence_starts(datetime(2026, 1, 1, 0, 0), "daily", date(2027, 1, 2))


def test_custom_every_two_days():
    starts = occurrence_starts(
        datetime(2026, 10, 1, 6, 0),
        "custom",
        date(2026, 10, 7),
        interval_days=2,
    )
    assert [row.date() for row in starts] == [
        date(2026, 10, 1),
        date(2026, 10, 3),
        date(2026, 10, 5),
        date(2026, 10, 7),
    ]


def test_custom_requires_interval_days():
    with pytest.raises(ValueError, match="interval_days"):
        occurrence_starts(datetime(2026, 10, 1, 6, 0), "custom", date(2026, 10, 7))
