"""Item summary hub — empty workspace / brand-new item."""
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

from app.dao.inventory import inventory_dao
from app.dao.inventory_ledger import inventory_ledger_dao
from app.dao.machine_item import machine_item_dao
from app.dao.machine_item_ledger import machine_item_ledger_dao
from app.dao.product import product_dao
from app.dao.product_ledger import product_ledger_dao
from app.managers.item_manager import item_manager
from app.schemas.item_summary import ItemSummaryResponse
from app.services.item_summary_service import item_summary_service


def _empty_query():
    q = MagicMock()
    q.all.return_value = []
    q.scalar.return_value = 0
    q.first.return_value = None
    q.join.return_value = q
    q.outerjoin.return_value = q
    q.filter.return_value = q
    q.order_by.return_value = q
    q.limit.return_value = q
    q.select_from.return_value = q
    return q


def _new_item(*, item_id: int = 1, workspace_id: int = 99) -> MagicMock:
    item = MagicMock()
    item.id = item_id
    item.workspace_id = workspace_id
    item.name = "Raw Cotton"
    item.description = None
    item.unit = "kg"
    item.sku = None
    item.is_active = True
    item.created_at = datetime.now(timezone.utc)
    item.updated_at = None
    item.created_by = 7
    item.updated_by = None
    return item


def test_summary_for_new_item_in_empty_workspace_serializes() -> None:
    item = _new_item()
    db = MagicMock()
    db.query.return_value = _empty_query()

    with (
        patch.object(item_manager, "get_item", return_value=item),
        patch.object(item_manager, "get_tags_for_item", return_value=[]),
        patch.object(inventory_dao, "get_by_item", return_value=[]),
        patch.object(product_dao, "get_by_item", return_value=[]),
        patch.object(machine_item_dao, "get_by_item", return_value=[]),
        patch.object(inventory_ledger_dao, "get_by_workspace", return_value=[]),
        patch.object(product_ledger_dao, "get_by_workspace", return_value=[]),
        patch.object(machine_item_ledger_dao, "get_by_item", return_value=[]),
    ):
        result = item_summary_service.get_summary(db, item_id=item.id, workspace_id=item.workspace_id)

    payload = ItemSummaryResponse.model_validate(result)
    assert payload.item.name == "Raw Cotton"
    assert payload.item.tags == []
    assert payload.kpis.storage_qty_total == 0
    assert payload.kpis.factory_count_with_stock == 0
    assert payload.inventory_rows == []
    assert payload.product_rows == []
    assert payload.machine_placements == []
    assert payload.recent_activity == []
    assert payload.order_stats.all_time.line_count == 0
    assert payload.order_stats.all_time.total_spend == Decimal("0")
    assert payload.pricing.last_unit_price is None
    assert payload.supplier_stats.period.all_time.suppliers == []
    assert payload.usage_counts.formula_count == 0


def test_summary_missing_item_raises_not_found() -> None:
    from app.core.exceptions import NotFoundError

    db = MagicMock()
    with patch.object(item_manager, "get_item", return_value=None):
        try:
            item_summary_service.get_summary(db, item_id=404, workspace_id=99)
        except NotFoundError as exc:
            assert "404" in str(exc)
        else:
            raise AssertionError("expected NotFoundError")
