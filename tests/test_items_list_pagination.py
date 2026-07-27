"""Tests for paginated item catalog list."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.dao.item import _apply_item_catalog_filters
from app.models.item import Item
from app.schemas.item import ItemListResponse
from app.services.item_service import ItemService


def test_item_list_response_has_more_when_more_rows_exist() -> None:
    result = ItemListResponse(
        items=[],
        total=120,
        skip=50,
        limit=50,
        has_more=50 + 50 < 120,
    )
    assert result.has_more is True


def test_item_list_response_has_more_false_on_last_page() -> None:
    result = ItemListResponse(
        items=[],
        total=75,
        skip=50,
        limit=50,
        has_more=50 + 25 < 75,
    )
    assert result.has_more is False


def test_service_items_page_has_more_from_manager_counts() -> None:
    service = ItemService()
    db = MagicMock()
    item = MagicMock()
    item.id = 1
    item.workspace_id = 1
    item.name = "Wool"
    item.description = None
    item.unit = "lbs"
    item.sku = None
    item.is_active = True
    item.created_at = datetime.now(timezone.utc)
    item.updated_at = None
    item.created_by = None
    item.updated_by = None

    with patch.object(service.item_manager, "count_items_filtered", return_value=120), patch.object(
        service.item_manager, "list_items_filtered", return_value=[item]
    ), patch.object(service.item_manager, "get_tags_for_items", return_value={1: []}) as bulk_tags:
        result = service.get_items_page(db, workspace_id=1, skip=50, limit=50)

    bulk_tags.assert_called_once_with(session=db, item_ids=[1], workspace_id=1)

    assert result.total == 120
    assert result.has_more is True
    assert len(result.items) == 1


def test_service_items_page_uses_bulk_tag_lookup_once() -> None:
    service = ItemService()
    db = MagicMock()

    def make_item(item_id: int) -> MagicMock:
        item = MagicMock()
        item.id = item_id
        item.workspace_id = 1
        item.name = f"Item {item_id}"
        item.description = None
        item.unit = "kg"
        item.sku = None
        item.is_active = True
        item.created_at = datetime.now(timezone.utc)
        item.updated_at = None
        item.created_by = None
        item.updated_by = None
        return item

    items = [make_item(i) for i in range(1, 4)]

    with patch.object(service.item_manager, "count_items_filtered", return_value=3), patch.object(
        service.item_manager, "list_items_filtered", return_value=items
    ), patch.object(
        service.item_manager, "get_tags_for_items", return_value={1: [], 2: [], 3: []}
    ) as bulk_tags, patch.object(service.item_manager, "get_tags_for_item") as single_tags:
        service.get_items_page(db, workspace_id=1, skip=0, limit=50)

    bulk_tags.assert_called_once_with(session=db, item_ids=[1, 2, 3], workspace_id=1)
    single_tags.assert_not_called()


def test_apply_item_catalog_filters_search_includes_unit() -> None:
    from sqlalchemy.sql.elements import BinaryExpression

    query = MagicMock()
    query.session = MagicMock()
    captured_clauses: list = []

    def capture_or(*clauses):
        captured_clauses.extend(clauses)
        return MagicMock()

    with patch("app.dao.item.or_", side_effect=capture_or):
        _apply_item_catalog_filters(query, workspace_id=1, search="kg")

    assert captured_clauses
    assert any(
        isinstance(clause, BinaryExpression) and getattr(clause.left, "key", None) == "unit"
        for clause in captured_clauses
    )


def test_apply_item_catalog_filters_unit() -> None:
    query = MagicMock()
    _apply_item_catalog_filters(
        query,
        workspace_id=1,
        unit="lbs",
    )
    assert query.filter.called


def test_apply_item_catalog_filters_search() -> None:
    query = MagicMock()
    query.session = MagicMock()
    _apply_item_catalog_filters(
        query,
        workspace_id=1,
        search="wool",
    )
    assert query.filter.called


def test_items_openapi_uses_paginated_response_model() -> None:
    from app.main import app

    schema = app.openapi()["paths"]["/api/v1/items/"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]
    assert schema["$ref"].endswith("ItemListResponse")


def test_items_units_route_exists() -> None:
    from app.main import app

    assert "/api/v1/items/units/" in app.openapi()["paths"]
