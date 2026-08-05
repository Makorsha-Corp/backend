"""Tests for storage incoming order summary aggregation."""
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.managers.inventory_manager import InventoryManager


def _status(name: str) -> MagicMock:
    s = MagicMock()
    s.name = name
    return s


def _po(
    *,
    po_id: int,
    po_number: str,
    workflow_id: int = 1,
    status_id: int = 2,
    status_name: str = "Receiving",
) -> MagicMock:
    po = MagicMock()
    po.id = po_id
    po.po_number = po_number
    po.order_workflow_id = workflow_id
    po.current_status_id = status_id
    po.current_status = _status(status_name)
    return po


def _po_item(*, po_id: int, item_id: int, ordered: str, received: str = "0") -> MagicMock:
    line = MagicMock()
    line.purchase_order_id = po_id
    line.item_id = item_id
    line.quantity_ordered = Decimal(ordered)
    line.quantity_received = Decimal(received)
    return line


def _transfer(
    *,
    tr_id: int,
    tr_number: str,
    status_name: str = "In transit",
) -> MagicMock:
    tr = MagicMock()
    tr.id = tr_id
    tr.transfer_number = tr_number
    tr.current_status = _status(status_name)
    return tr


def _tr_item(*, tr_id: int, item_id: int, qty: str) -> MagicMock:
    line = MagicMock()
    line.transfer_order_id = tr_id
    line.item_id = item_id
    line.quantity = Decimal(qty)
    return line


@patch("app.managers.inventory_manager.transfer_order_item_dao")
@patch("app.managers.inventory_manager.transfer_order_dao")
@patch("app.managers.inventory_manager.purchase_order_item_dao")
@patch("app.managers.inventory_manager.purchase_order_dao")
@patch("app.managers.inventory_manager.factory_dao")
@patch("app.managers.inventory_manager.terminal_status_ids_by_workflow")
def test_incoming_summary_po_partial_and_transfer(
    mock_terminal,
    mock_factory_dao,
    mock_po_dao,
    mock_po_item_dao,
    mock_tr_dao,
    mock_tr_item_dao,
) -> None:
    mock_factory_dao.get_by_id_and_workspace.return_value = MagicMock(id=5)
    mock_terminal.return_value = {1: 99}  # terminal status 99

    po = _po(po_id=10, po_number="PO-2026-004", status_id=2)
    mock_po_dao.list_for_destination.return_value = [po]
    mock_po_item_dao.get_by_purchase_order_ids.return_value = [
        _po_item(po_id=10, item_id=50, ordered="100", received="50"),
    ]

    tr = _transfer(tr_id=20, tr_number="TR-2026-012")
    mock_tr_dao.list_inbound_to_storage_incomplete.return_value = [tr]
    mock_tr_item_dao.get_by_transfer_order_ids.return_value = [
        _tr_item(tr_id=20, item_id=50, qty="70"),
    ]

    mgr = InventoryManager()
    result = mgr.get_incoming_summary_for_factory(
        MagicMock(), workspace_id=1, factory_id=5
    )

    assert len(result) == 1
    summary = result[0]
    assert summary.factory_id == 5
    assert summary.item_id == 50
    assert summary.total_pending_qty == Decimal("120")
    assert summary.order_count == 2
    kinds = {line.order_kind for line in summary.orders}
    assert kinds == {"purchase", "transfer"}
    po_line = next(o for o in summary.orders if o.order_kind == "purchase")
    assert po_line.pending_qty == Decimal("50")
    assert po_line.order_number == "PO-2026-004"


@patch("app.managers.inventory_manager.transfer_order_item_dao")
@patch("app.managers.inventory_manager.transfer_order_dao")
@patch("app.managers.inventory_manager.purchase_order_item_dao")
@patch("app.managers.inventory_manager.purchase_order_dao")
@patch("app.managers.inventory_manager.factory_dao")
@patch("app.managers.inventory_manager.terminal_status_ids_by_workflow")
def test_incoming_summary_excludes_terminal_po(
    mock_terminal,
    mock_factory_dao,
    mock_po_dao,
    mock_po_item_dao,
    mock_tr_dao,
    mock_tr_item_dao,
) -> None:
    mock_factory_dao.get_by_id_and_workspace.return_value = MagicMock(id=5)
    mock_terminal.return_value = {1: 99}

    terminal_po = _po(po_id=10, po_number="PO-DONE", status_id=99)
    mock_po_dao.list_for_destination.return_value = [terminal_po]
    mock_tr_dao.list_inbound_to_storage_incomplete.return_value = []
    mock_tr_item_dao.get_by_transfer_order_ids.return_value = []

    mgr = InventoryManager()
    result = mgr.get_incoming_summary_for_factory(
        MagicMock(), workspace_id=1, factory_id=5
    )

    assert result == []
    mock_po_item_dao.get_by_purchase_order_ids.assert_not_called()


@patch("app.managers.inventory_manager.factory_dao")
def test_incoming_summary_factory_not_found(mock_factory_dao) -> None:
    mock_factory_dao.get_by_id_and_workspace.return_value = None
    mgr = InventoryManager()
    with pytest.raises(HTTPException) as exc:
        mgr.get_incoming_summary_for_factory(
            MagicMock(), workspace_id=1, factory_id=999
        )
    assert exc.value.status_code == 404


@patch("app.managers.inventory_manager.transfer_order_item_dao")
@patch("app.managers.inventory_manager.transfer_order_dao")
@patch("app.managers.inventory_manager.purchase_order_item_dao")
@patch("app.managers.inventory_manager.purchase_order_dao")
@patch("app.managers.inventory_manager.factory_dao")
@patch("app.managers.inventory_manager.terminal_status_ids_by_workflow")
def test_incoming_summary_workspace_wide(
    mock_terminal,
    mock_factory_dao,
    mock_po_dao,
    mock_po_item_dao,
    mock_tr_dao,
    mock_tr_item_dao,
) -> None:
    factory_a = MagicMock(id=5)
    factory_b = MagicMock(id=7)
    mock_factory_dao.get_active_factories.return_value = [factory_a, factory_b]
    mock_factory_dao.get_by_id_and_workspace.side_effect = lambda _s, *, id, workspace_id: (
        factory_a if id == 5 else factory_b if id == 7 else None
    )
    mock_terminal.return_value = {1: 99}
    mock_po_dao.list_for_destination.return_value = []
    mock_tr_dao.list_inbound_to_storage_incomplete.return_value = []
    mock_tr_item_dao.get_by_transfer_order_ids.return_value = []

    po = _po(po_id=10, po_number="PO-2026-010", status_id=2)
    mock_po_item_dao.get_by_purchase_order_ids.return_value = [
        _po_item(po_id=10, item_id=50, ordered="20", received="0"),
    ]

    def list_for_destination(_session, *, workspace_id, destination_type, destination_id):
        if destination_id == 5:
            return [po]
        return []

    mock_po_dao.list_for_destination.side_effect = list_for_destination

    mgr = InventoryManager()
    result = mgr.get_incoming_summary(MagicMock(), workspace_id=1)

    assert len(result) == 1
    assert result[0].factory_id == 5
    assert result[0].item_id == 50
    assert result[0].total_pending_qty == Decimal("20")
