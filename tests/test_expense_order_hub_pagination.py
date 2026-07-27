"""Tests for paginated expense order hub list."""

from unittest.mock import MagicMock, patch

from app.schemas.expense_order import ExpenseOrderListResponse
from app.services.expense_order_service import ExpenseOrderService


def test_expense_order_list_response_has_more() -> None:
    result = ExpenseOrderListResponse(
        items=[],
        total=120,
        skip=50,
        limit=50,
        has_more=True,
    )
    assert result.has_more is True


def test_service_list_page_uses_hub_count_and_list() -> None:
    service = ExpenseOrderService()
    db = MagicMock()
    eo = MagicMock()
    eo.id = 1

    with patch.object(service.manager, "count_expense_orders_for_hub", return_value=75) as count_hub, patch.object(
        service.manager, "list_expense_orders_for_hub", return_value=[eo]
    ) as list_hub, patch("app.schemas.expense_order.ExpenseOrderListResponse") as list_response:
        list_response.return_value = ExpenseOrderListResponse(
            items=[], total=75, skip=50, limit=50, has_more=False
        )
        result = service.list_expense_orders_page(
            db, workspace_id=1, skip=50, limit=50, exclude_voided=True
        )

    count_hub.assert_called_once()
    list_hub.assert_called_once()
    assert result.total == 75
    assert result.has_more is False


def test_expense_orders_stats_route_registered() -> None:
    from app.main import app

    assert "/api/v1/expense-orders/stats/" in app.openapi()["paths"]
