"""Tests for paginated inventory list and stats."""

from decimal import Decimal
from unittest.mock import MagicMock, patch

from app.models.enums import InventoryTypeEnum
from app.schemas.inventory import InventoryListResponse, InventoryStatsResponse
from app.services.inventory_service import InventoryService


def test_inventory_list_response_has_more() -> None:
    result = InventoryListResponse(
        items=[],
        total=120,
        skip=50,
        limit=50,
        has_more=True,
    )
    assert result.has_more is True


def test_service_inventory_page_uses_count_and_list() -> None:
    service = InventoryService()
    db = MagicMock()

    with patch.object(service.manager, "get_inventory_page") as get_page:
        get_page.return_value = InventoryListResponse(
            items=[],
            total=75,
            skip=50,
            limit=50,
            has_more=True,
        )
        result = service.get_inventory_page(
            db,
            workspace_id=1,
            skip=50,
            limit=50,
            search="yarn",
        )

    get_page.assert_called_once()
    assert result.total == 75
    assert result.has_more is True


def test_manager_inventory_page_calls_filtered_dao() -> None:
    from app.managers.inventory_manager import InventoryManager

    manager = InventoryManager()
    session = MagicMock()

    with patch.object(manager.inv_dao, "list_filtered", return_value=[]) as list_filtered, patch.object(
        manager.inv_dao, "count_filtered", return_value=0
    ):
        result = manager.get_inventory_page(
            session,
            workspace_id=1,
            search="moosh",
            include_zero_qty=True,
            skip=10,
            limit=25,
        )

    list_filtered.assert_called_once_with(
        session,
        workspace_id=1,
        inventory_type=None,
        factory_id=None,
        item_id=None,
        search="moosh",
        include_zero_qty=True,
        skip=10,
        limit=25,
    )
    assert result.total == 0
    assert result.has_more is False


def test_manager_inventory_stats_shape() -> None:
    from app.managers.inventory_manager import InventoryManager

    manager = InventoryManager()
    session = MagicMock()

    with patch.object(
        manager.inv_dao,
        "stats_filtered",
        return_value=(3, 40, Decimal("99.50"), [(InventoryTypeEnum.STORAGE, 2, 40)]),
    ):
        result = manager.get_inventory_stats(session, workspace_id=1)

    assert isinstance(result, InventoryStatsResponse)
    assert result.records == 3
    assert result.total_qty == 40
    assert result.estimated_value == Decimal("99.50")
    assert len(result.by_type) == 1
    assert result.by_type[0].inventory_type == InventoryTypeEnum.STORAGE
    assert result.by_type[0].unique_item_count == 2


def test_inventory_stats_route_registered() -> None:
    from app.main import app

    paths = app.openapi()["paths"]
    assert "/api/v1/inventory/stats/" in paths


def test_inventory_list_route_returns_envelope() -> None:
    from app.main import app

    schema = app.openapi()["paths"]["/api/v1/inventory/"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]
    assert schema["$ref"].endswith("InventoryListResponse")
