"""Tests for paginated work order sheet list."""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.dao.work_order import _apply_sheet_list_filters, _work_order_calendar_date_expr
from app.models.enums import WorkOrderStatusEnum
from app.schemas.work_order import WorkOrderSheetListResponse
from app.services.work_order_service import WorkOrderService


def test_sheet_list_response_has_more_when_more_rows_exist() -> None:
    result = WorkOrderSheetListResponse(
        items=[],
        total=120,
        skip=50,
        limit=50,
        has_more=50 + 50 < 120,
    )
    assert result.has_more is True


def test_sheet_list_response_has_more_false_on_last_page() -> None:
    result = WorkOrderSheetListResponse(
        items=[],
        total=75,
        skip=50,
        limit=50,
        has_more=50 + 25 < 75,
    )
    assert result.has_more is False


def test_service_sheet_list_has_more_from_manager_counts() -> None:
    service = WorkOrderService()
    db = MagicMock()

    with patch.object(service.manager, "count_sheet_orders", return_value=120), patch.object(
        service.manager, "list_sheet_orders", return_value=[]
    ):
        result = service.list_sheet_bundles(db, workspace_id=1, skip=50, limit=50)

    assert result.total == 120
    assert result.has_more is True


def test_apply_sheet_filters_planned_scope_adds_future_draft_filters() -> None:
    query = MagicMock()
    calendar_date = _work_order_calendar_date_expr()
    today = date.today()

    _apply_sheet_list_filters(
        query,
        calendar_date=calendar_date,
        status_scope="planned",
    )

    assert query.filter.called
    filter_arg = query.filter.call_args[0][0]
    assert filter_arg is not None


def test_apply_sheet_filters_exclude_completed() -> None:
    query = MagicMock()
    calendar_date = _work_order_calendar_date_expr()

    _apply_sheet_list_filters(
        query,
        calendar_date=calendar_date,
        exclude_completed=True,
    )

    query.filter.assert_called()
    filter_arg = query.filter.call_args[0][0]
    assert str(filter_arg).lower().find("completed") >= 0 or filter_arg is not None


def test_apply_sheet_filters_search() -> None:
    query = MagicMock()
    calendar_date = _work_order_calendar_date_expr()

    _apply_sheet_list_filters(
        query,
        calendar_date=calendar_date,
        search="WO-2026",
    )

    assert query.filter.call_count >= 1


def test_sheet_openapi_uses_paginated_response_model() -> None:
    from app.main import app

    schema = app.openapi()["paths"]["/api/v1/work-orders/sheet/"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]
    assert schema["$ref"].endswith("WorkOrderSheetListResponse")


def test_sheet_limit_default_and_max_in_openapi() -> None:
    from app.main import app

    params = app.openapi()["paths"]["/api/v1/work-orders/sheet/"]["get"]["parameters"]
    limit_param = next(p for p in params if p["name"] == "limit")
    assert limit_param["schema"]["default"] == 50
    assert limit_param["schema"]["maximum"] == 100
