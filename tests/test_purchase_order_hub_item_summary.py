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
    ), patch(
        "app.dao.purchase_order.purchase_order_item_dao.preview_names_by_purchase_order_ids",
        return_value={1: ["Cotton Yarn", "Bearing Seal"]},
    ):
        service._attach_item_summaries(db, workspace_id=10, orders=[po1, po2])

    assert po1.item_count == 2
    assert po1.quantity_ordered_total == Decimal("15")
    assert po1.quantity_received_total == Decimal("5")
    assert po1.item_names_preview == ["Cotton Yarn", "Bearing Seal"]
    assert po2.item_count == 0
    assert po2.quantity_ordered_total == Decimal("0")
    assert po2.quantity_received_total == Decimal("0")
    assert po2.item_names_preview == []


def test_preview_names_respects_line_order_and_cap() -> None:
    from app.dao.purchase_order import purchase_order_item_dao

    db = MagicMock()
    rows = [
        (1, 10, "Alpha"),
        (1, 11, "Beta"),
        (1, 12, "Gamma"),
        (1, 13, "Delta"),
        (1, 14, "Epsilon"),
        (2, 20, "Solo"),
    ]
    db.query.return_value.join.return_value.filter.return_value.order_by.return_value.all.return_value = (
        rows
    )

    result = purchase_order_item_dao.preview_names_by_purchase_order_ids(
        db, workspace_id=10, purchase_order_ids=[1, 2], limit=4
    )

    assert result[1] == ["Alpha", "Beta", "Gamma", "Delta"]
    assert result[2] == ["Solo"]


def test_preview_names_fallback_when_item_name_missing() -> None:
    from app.dao.purchase_order import purchase_order_item_dao

    db = MagicMock()
    db.query.return_value.join.return_value.filter.return_value.order_by.return_value.all.return_value = [
        (1, 99, None),
    ]

    result = purchase_order_item_dao.preview_names_by_purchase_order_ids(
        db, workspace_id=10, purchase_order_ids=[1]
    )

    assert result[1] == ["Item #99"]
