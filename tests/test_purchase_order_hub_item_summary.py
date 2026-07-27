"""Tests for purchase order hub list item summary fields."""

from decimal import Decimal
from unittest.mock import MagicMock, patch

from app.services.purchase_order_service import PurchaseOrderService


def test_attach_item_summaries_sets_transient_fields() -> None:
    service = PurchaseOrderService()
    db = MagicMock()
    po1 = MagicMock()
    po1.id = 1
    po2 = MagicMock()
    po2.id = 2

    with patch(
        "app.dao.purchase_order.purchase_order_item_dao.summarize_by_purchase_order_ids",
        return_value={
            1: {
                "item_count": 2,
                "quantity_ordered_total": Decimal("15"),
                "quantity_received_total": Decimal("5"),
            },
        },
    ):
        service._attach_item_summaries(db, workspace_id=10, orders=[po1, po2])

    assert po1.item_count == 2
    assert po1.quantity_ordered_total == Decimal("15")
    assert po1.quantity_received_total == Decimal("5")
    assert po2.item_count == 0
    assert po2.quantity_ordered_total == Decimal("0")
    assert po2.quantity_received_total == Decimal("0")
