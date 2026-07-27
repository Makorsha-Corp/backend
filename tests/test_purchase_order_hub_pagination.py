"""Tests for paginated purchase order hub list."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from app.schemas.purchase_order import PurchaseOrderListResponse
from app.services.purchase_order_service import PurchaseOrderService


def test_purchase_order_list_response_has_more() -> None:
    result = PurchaseOrderListResponse(
        items=[],
        total=120,
        skip=50,
        limit=50,
        has_more=True,
    )
    assert result.has_more is True


def test_service_list_page_uses_hub_count_and_list() -> None:
    service = PurchaseOrderService()
    db = MagicMock()
    po = MagicMock()
    po.id = 1

    with patch.object(service.manager, "count_purchase_orders_for_hub", return_value=75) as count_hub, patch.object(
        service.manager, "list_purchase_orders_for_hub", return_value=[po]
    ) as list_hub, patch.object(service, "_prepare_listed_orders", return_value=[]):
        result = service.list_purchase_orders_page(
            db, workspace_id=1, skip=50, limit=50, exclude_voided=True
        )

    count_hub.assert_called_once()
    list_hub.assert_called_once()
    assert result.total == 75
    assert result.has_more is True
    assert len(result.items) == 0


def test_purchase_orders_stats_route_registered() -> None:
    from app.main import app

    assert "/api/v1/purchase-orders/stats/" in app.openapi()["paths"]
