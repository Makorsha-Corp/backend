"""Ensure sheet view API routes are registered on the FastAPI app."""

from app.main import app

SHEET_PATH = "/api/v1/work-orders/sheet/"
SHEET_DAILY_COUNTS_PATH = "/api/v1/work-orders/sheet/daily-counts/"
SHEET_ENTRY_PATH = "/api/v1/work-orders/sheet-entry/"
GENERATE_DRAFTS_PATH = "/api/v1/work-order-templates/generate-drafts/"


def _openapi_paths() -> dict:
    return app.openapi()["paths"]


def test_work_order_sheet_get_route_registered() -> None:
    paths = _openapi_paths()
    assert SHEET_PATH in paths
    assert "get" in paths[SHEET_PATH]


def test_work_order_sheet_daily_counts_get_route_registered() -> None:
    paths = _openapi_paths()
    assert SHEET_DAILY_COUNTS_PATH in paths
    assert "get" in paths[SHEET_DAILY_COUNTS_PATH]


def test_work_order_sheet_entry_post_route_registered() -> None:
    paths = _openapi_paths()
    assert SHEET_ENTRY_PATH in paths
    assert "post" in paths[SHEET_ENTRY_PATH]


def test_work_order_template_generate_drafts_route_registered() -> None:
    paths = _openapi_paths()
    assert GENERATE_DRAFTS_PATH in paths
    assert "post" in paths[GENERATE_DRAFTS_PATH]
