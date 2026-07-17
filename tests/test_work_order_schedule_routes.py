"""Ensure work order schedule API routes are registered on the FastAPI app."""

from app.main import app

SCHEDULES_PATH = "/api/v1/work-order-schedules/"
STAGE_DAY_PATH = "/api/v1/work-order-schedules/stage-day/"


def _openapi_paths() -> dict:
    return app.openapi()["paths"]


def test_work_order_schedules_list_route_registered() -> None:
    paths = _openapi_paths()
    assert SCHEDULES_PATH in paths
    assert "get" in paths[SCHEDULES_PATH]


def test_work_order_schedules_stage_day_route_registered() -> None:
    paths = _openapi_paths()
    assert STAGE_DAY_PATH in paths
    assert "post" in paths[STAGE_DAY_PATH]


def test_work_order_schedule_confirm_route_registered() -> None:
    paths = _openapi_paths()
    confirm_path = "/api/v1/work-order-schedules/{schedule_id}/confirm/"
    assert confirm_path in paths
    assert "post" in paths[confirm_path]


def test_work_order_schedule_cancel_route_registered() -> None:
    paths = _openapi_paths()
    cancel_path = "/api/v1/work-order-schedules/{schedule_id}/cancel/"
    assert cancel_path in paths
    assert "post" in paths[cancel_path]
