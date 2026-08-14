"""Tests for IANA timezone validation."""
import pytest

from app.utils.timezone_validate import is_valid_iana_timezone


def test_valid_timezones():
    assert is_valid_iana_timezone("Asia/Dhaka")
    assert is_valid_iana_timezone("America/New_York")
    assert is_valid_iana_timezone("UTC")


def test_invalid_timezones():
    assert not is_valid_iana_timezone("")
    assert not is_valid_iana_timezone("Not/AZone")
    assert not is_valid_iana_timezone("GMT+6")
