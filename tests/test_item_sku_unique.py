"""SKU uniqueness for catalog items."""
from unittest.mock import MagicMock, patch

import pytest

from app.core.exceptions import ConflictError
from app.managers.item_manager import ItemManager
from app.schemas.item import ItemCreate, ItemUpdate
from app.utils.item_name_normalize import normalize_item_sku


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("FG-YARN-20NE", "FG-YARN-20NE"),
        ("  FG-001  ", "FG-001"),
        ("", None),
        ("   ", None),
        (None, None),
    ],
)
def test_normalize_item_sku(raw: str | None, expected: str | None) -> None:
    assert normalize_item_sku(raw) == expected


def test_create_item_rejects_duplicate_sku() -> None:
    manager = ItemManager()
    session = MagicMock()
    existing = MagicMock()
    existing.id = 10
    existing.name = "20Ne Combed Cotton Yarn"

    with patch.object(
        manager.item_dao, "get_by_sku_in_workspace", return_value=existing
    ), patch.object(manager.item_dao, "create") as create_mock:
        with pytest.raises(ConflictError, match="FG-YARN-20NE"):
            manager.create_item(
                session,
                ItemCreate(name="30Ne Yarn", unit="kg", sku="FG-YARN-20NE"),
                workspace_id=1,
                user_id=1,
            )
        create_mock.assert_not_called()


def test_create_item_allows_blank_sku_without_lookup() -> None:
    manager = ItemManager()
    session = MagicMock()
    created = MagicMock()

    with patch.object(
        manager.item_dao, "get_by_sku_in_workspace"
    ) as sku_lookup, patch.object(manager.item_dao, "create", return_value=created) as create_mock:
        result = manager.create_item(
            session,
            ItemCreate(name="Ad-hoc item", unit="kg", sku="  "),
            workspace_id=1,
            user_id=1,
        )

    sku_lookup.assert_not_called()
    create_mock.assert_called_once()
    assert result is created
    call_sku = create_mock.call_args.kwargs["obj_in"]["sku"]
    assert call_sku is None


def test_update_item_allows_same_sku_on_self() -> None:
    manager = ItemManager()
    session = MagicMock()
    item = MagicMock()
    item.id = 5
    item.workspace_id = 1
    item.sku = "FG-001"
    item.is_active = True
    updated = MagicMock()

    with patch.object(manager.item_dao, "get", return_value=item), patch.object(
        manager.item_dao, "get_by_sku_in_workspace", return_value=None
    ) as sku_lookup, patch.object(manager.item_dao, "update", return_value=updated):
        manager.update_item(
            session,
            item_id=5,
            item_data=ItemUpdate(sku="FG-001"),
            workspace_id=1,
            user_id=1,
        )

    sku_lookup.assert_called_once()
    assert sku_lookup.call_args.kwargs["exclude_item_id"] == 5
