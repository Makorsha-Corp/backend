"""Calendar API route registration and service validation."""

from datetime import date

import pytest

from app.main import app
from app.services.calendar_service import calendar_service

CALENDAR_EVENTS_PATH = "/api/v1/calendar/events"


def test_calendar_events_route_registered() -> None:
    paths = app.openapi()["paths"]
    assert CALENDAR_EVENTS_PATH in paths
    assert "get" in paths[CALENDAR_EVENTS_PATH]


def test_calendar_service_rejects_inverted_range() -> None:
    with pytest.raises(ValueError, match="start must be on or before end"):
        calendar_service.get_events(
            db=None,  # type: ignore[arg-type]
            workspace_id=1,
            start=date(2026, 2, 1),
            end=date(2026, 1, 1),
        )
