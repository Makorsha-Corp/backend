"""Tests for paginated transfer order hub list."""

from unittest.mock import MagicMock, patch

from app.schemas.transfer_order import TransferOrderListResponse
from app.services.transfer_order_service import TransferOrderService


def test_transfer_order_list_response_has_more() -> None:
    result = TransferOrderListResponse(
        items=[],
        total=120,
        skip=50,
        limit=50,
        has_more=True,
    )
    assert result.has_more is True


def test_service_list_page_uses_hub_count_and_list() -> None:
    service = TransferOrderService()
    db = MagicMock()
    to = MagicMock()
    to.id = 1

    with patch.object(service.manager, "count_transfer_orders_for_hub", return_value=75) as count_hub, patch.object(
        service.manager, "list_transfer_orders_for_hub", return_value=[to]
    ) as list_hub, patch("app.schemas.transfer_order.TransferOrderListResponse") as list_response:
        list_response.return_value = TransferOrderListResponse(
            items=[], total=75, skip=50, limit=50, has_more=False
        )
        result = service.list_transfer_orders_page(
            db, workspace_id=1, skip=50, limit=50, exclude_complete=True
        )

    count_hub.assert_called_once()
    list_hub.assert_called_once()
    assert result.total == 75
    assert result.has_more is False


def test_transfer_orders_stats_route_registered() -> None:
    from app.main import app

    assert "/api/v1/transfer-orders/stats/" in app.openapi()["paths"]
