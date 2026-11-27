"""Unit tests for app/utils/time.py — implements tests/unit/utils/time.cases.md."""
# ruff: noqa: DTZ001  (prescribed by the cards: naive datetimes)
import datetime
from datetime import timedelta, timezone
from unittest.mock import patch

import pytest

from app.utils.time import utcnow

# Convention: fake local zone LOCAL = UTC+06:00 (deliberately not UTC).
LOCAL = timezone(timedelta(hours=6))


def real_bound():
    """Convention "real-clock bound" (naive-UTC reading) from the real, unpatched datetime."""
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


class FakeDatetime(datetime.datetime):
    """Convention FROZEN(I): every "current time" entry point answers from one aware instant."""

    instant: datetime.datetime  # set by the `frozen` fixture

    @classmethod
    def now(cls, tz=None):
        if tz is not None:
            return cls.instant.astimezone(tz)
        return cls.instant.astimezone(LOCAL).replace(tzinfo=None)

    @classmethod
    def utcnow(cls):
        return cls.instant.astimezone(timezone.utc).replace(tzinfo=None)

    @classmethod
    def today(cls):
        return cls.now(None)


@pytest.fixture
def frozen():
    """Convention FROZEN(I): patches app.utils.time.datetime; call frozen(I) to set/move the instant."""

    def set_instant(instant):
        FakeDatetime.instant = instant

    with patch("app.utils.time.datetime", FakeDatetime):
        yield set_instant


# --- utcnow -----------------------------------------------------------------


def test_time_u_01__real_clock_between_bounds():
    """TIME-U-01 — real clock: result is a naive datetime between naive-UTC bounds.
    Rules: utcnow R1, R2."""
    before = real_bound()
    result = utcnow()
    after = real_bound()
    assert isinstance(result, datetime.datetime)
    assert result.tzinfo is None
    assert before <= result <= after


def test_time_u_02__frozen_utc_instant(frozen):
    """TIME-U-02 — frozen at a UTC instant: exact naive value, microseconds kept.
    Rules: utcnow R1, R3."""
    frozen(datetime.datetime(2026, 1, 15, 10, 30, 45, 123456, tzinfo=timezone.utc))
    result = utcnow()
    assert result == datetime.datetime(2026, 1, 15, 10, 30, 45, 123456)
    assert result.tzinfo is None
    assert result.microsecond == 123456


def test_time_u_03__converted_to_utc_not_local(frozen):
    """TIME-U-03 — frozen at a +06:00 instant with local zone +06:00: result is UTC, not local.
    Rules: utcnow R2, R3."""
    frozen(datetime.datetime(2026, 1, 15, 16, 30, 45, 123456, tzinfo=LOCAL))
    result = utcnow()
    assert result == datetime.datetime(2026, 1, 15, 10, 30, 45, 123456)
    assert result != datetime.datetime(2026, 1, 15, 16, 30, 45, 123456)
    assert result.tzinfo is None


def test_time_u_04__utc_conversion_crosses_year(frozen):
    """TIME-U-04 — UTC conversion crosses day/month/year boundary.
    Rules: utcnow R3."""
    frozen(datetime.datetime(2026, 1, 1, 3, 15, 0, 1, tzinfo=LOCAL))
    result = utcnow()
    assert result == datetime.datetime(2025, 12, 31, 21, 15, 0, 1)
    assert result.microsecond == 1
    assert result.tzinfo is None


def test_time_u_05__last_microsecond_not_rounded(frozen):
    """TIME-U-05 — last microsecond of a day is neither rounded up nor truncated.
    Rules: utcnow R3."""
    frozen(datetime.datetime(2026, 6, 30, 23, 59, 59, 999999, tzinfo=timezone.utc))
    result = utcnow()
    assert result == datetime.datetime(2026, 6, 30, 23, 59, 59, 999999)
    assert result.tzinfo is None


def test_time_u_06__successive_real_calls_non_decreasing():
    """TIME-U-06 — two real-clock calls in a row never go backwards; both naive.
    Rules: utcnow R4, R1."""
    first = utcnow()
    second = utcnow()
    assert second >= first
    assert first.tzinfo is None
    assert second.tzinfo is None


def test_time_u_07__each_call_reads_clock_afresh(frozen):
    """TIME-U-07 — advancing the frozen clock by 1 µs is seen by the next call (no caching).
    Rules: utcnow R4."""
    frozen(datetime.datetime(2026, 1, 15, 10, 30, 45, 123456, tzinfo=timezone.utc))
    first = utcnow()
    frozen(datetime.datetime(2026, 1, 15, 10, 30, 45, 123457, tzinfo=timezone.utc))
    second = utcnow()
    assert first == datetime.datetime(2026, 1, 15, 10, 30, 45, 123456)
    assert second == datetime.datetime(2026, 1, 15, 10, 30, 45, 123457)
    assert second - first == timedelta(microseconds=1)
