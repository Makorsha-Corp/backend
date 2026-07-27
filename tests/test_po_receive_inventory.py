"""Tests for PO receive-event inventory posting and void reversal."""
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.managers.po_receive_inventory import (
    PO_RECEIVE_EVENT_ITEM_SOURCE,
    post_receive_event_inventory,
    reverse_po_receive_inventory,
)
from app.managers import purchase_order_manager as po_manager_module


def _make_po(*, destination_type: str = 'storage', destination_id: int = 1) -> MagicMock:
    po = MagicMock()
    po.id = 100
    po.po_number = 'PO-2026-001'
    po.destination_type = destination_type
    po.destination_id = destination_id
    return po


def _make_line(*, line_id: int = 10, item_id: int = 50, line_number: int = 1) -> MagicMock:
    line = MagicMock()
    line.id = line_id
    line.item_id = item_id
    line.line_number = line_number
    line.unit_price = Decimal('12.50')
    return line


def _make_event_item(*, event_item_id: int = 500, po_item_id: int = 10, delta: str = '5') -> MagicMock:
    event_item = MagicMock()
    event_item.id = event_item_id
    event_item.po_item_id = po_item_id
    event_item.quantity_delta = Decimal(delta)
    return event_item


@patch('app.managers.po_receive_inventory.post_stock_in')
@patch('app.managers.po_receive_inventory._storage_ledger_exists', return_value=False)
@patch('app.managers.po_receive_inventory._machine_ledger_exists', return_value=False)
def test_post_receive_event_inventory_positive_delta(
    _mock_machine_exists,
    _mock_storage_exists,
    mock_stock_in,
) -> None:
    session = MagicMock()
    po = _make_po(destination_type='storage')
    line = _make_line()
    event_item = _make_event_item(delta='5')

    posted = post_receive_event_inventory(
        session, po, [(event_item, line)], workspace_id=1, user_id=7
    )

    assert posted == 1
    mock_stock_in.assert_called_once()
    assert mock_stock_in.call_args.kwargs['source_type'] == PO_RECEIVE_EVENT_ITEM_SOURCE
    assert mock_stock_in.call_args.kwargs['source_id'] == event_item.id
    assert mock_stock_in.call_args.kwargs['qty'] == 5


@patch('app.managers.po_receive_inventory.post_stock_out')
@patch('app.managers.po_receive_inventory._storage_ledger_exists', return_value=False)
@patch('app.managers.po_receive_inventory._machine_ledger_exists', return_value=False)
def test_post_receive_event_inventory_negative_correction(
    _mock_machine_exists,
    _mock_storage_exists,
    mock_stock_out,
) -> None:
    session = MagicMock()
    po = _make_po(destination_type='storage')
    line = _make_line()
    event_item = _make_event_item(delta='-2')

    posted = post_receive_event_inventory(
        session, po, [(event_item, line)], workspace_id=1, user_id=7
    )

    assert posted == 1
    mock_stock_out.assert_called_once()
    assert mock_stock_out.call_args.kwargs['qty'] == 2


@patch('app.managers.po_receive_inventory.post_stock_in')
@patch('app.managers.po_receive_inventory._storage_ledger_exists', return_value=False)
@patch('app.managers.po_receive_inventory._machine_ledger_exists', return_value=False)
def test_post_receive_event_skips_project_destination(
    _mock_machine_exists,
    _mock_storage_exists,
    mock_stock_in,
) -> None:
    session = MagicMock()
    po = _make_po(destination_type='project')
    line = _make_line()
    event_item = _make_event_item()

    posted = post_receive_event_inventory(
        session, po, [(event_item, line)], workspace_id=1, user_id=7
    )

    assert posted == 0
    mock_stock_in.assert_not_called()


@patch('app.managers.po_receive_inventory.post_stock_out')
@patch('app.managers.po_receive_inventory._reverse_legacy_line_posting', return_value=False)
@patch('app.managers.po_receive_inventory._reverse_event_item_posting', return_value=True)
def test_reverse_po_receive_inventory_counts_reversals(
    mock_reverse_event,
    _mock_reverse_legacy,
    _mock_stock_out,
) -> None:
    session = MagicMock()
    event_item = _make_event_item()
    line = _make_line()

    query = MagicMock()
    query.join.return_value = query
    query.filter.return_value = query
    query.order_by.return_value = query
    query.all.return_value = [event_item]
    session.query.return_value = query

    po = _make_po()
    count = reverse_po_receive_inventory(session, po, [line], workspace_id=1, user_id=7)

    assert count == 1
    mock_reverse_event.assert_called_once()


@patch('app.managers.po_receive_inventory.post_stock_out')
@patch('app.managers.po_receive_inventory._storage_ledger_exists')
@patch('app.managers.po_receive_inventory._machine_ledger_exists', return_value=False)
def test_post_receive_insufficient_stock_raises(
    _mock_machine_exists,
    mock_storage_exists,
    mock_stock_out,
) -> None:
    mock_storage_exists.return_value = False
    mock_stock_out.side_effect = HTTPException(
        status_code=400,
        detail='Insufficient stock (1 available, 2 requested)',
    )

    session = MagicMock()
    po = _make_po(destination_type='storage')
    line = _make_line()
    event_item = _make_event_item(delta='-2')

    with pytest.raises(HTTPException) as exc:
        post_receive_event_inventory(
            session, po, [(event_item, line)], workspace_id=1, user_id=7
        )

    assert 'Insufficient stock' in exc.value.detail


@patch.object(po_manager_module.purchase_order_manager, 'log_event')
@patch.object(po_manager_module.purchase_order_manager, 'sync_po_stage')
@patch.object(po_manager_module.purchase_order_manager, 'sync_po_paid')
@patch.object(po_manager_module.purchase_order_manager, '_all_items_fully_received', return_value=True)
@patch.object(po_manager_module.purchase_order_manager, '_is_po_complete_stage', return_value=False)
@patch.object(po_manager_module.purchase_order_manager, '_current_stage_name', return_value='Receiving')
@patch.object(po_manager_module.purchase_order_manager.item_dao, 'get_by_order')
@patch.object(po_manager_module.purchase_order_manager.po_dao, 'get_by_id_and_workspace')
def test_mark_order_complete_does_not_post_inventory(
    mock_get_po,
    mock_get_items,
    _mock_stage_name,
    _mock_is_complete,
    _mock_all_received,
    _mock_sync_paid,
    _mock_sync_stage,
    mock_log,
) -> None:
    session = MagicMock()
    po = _make_po()
    po.current_status_id = 3
    po.actual_delivery_date = None
    mock_get_po.return_value = po
    mock_get_items.return_value = [_make_line()]

    with patch.object(
        po_manager_module.purchase_order_manager,
        '_resolve_po_stage_status_id',
        return_value=99,
    ):
        po_manager_module.purchase_order_manager.mark_order_complete(
            session, po_id=100, workspace_id=1, user_id=7
        )

    logged_types = [call.args[3] for call in mock_log.call_args_list]
    assert 'order_completed' in logged_types
    assert 'inventory_posted' not in logged_types


@patch.object(po_manager_module.purchase_order_manager.item_dao, 'get_by_order', return_value=[])
def test_delete_purchase_order_blocks_when_receive_events_exist(mock_get_items) -> None:
    session = MagicMock()
    po = _make_po()
    po_manager_module.purchase_order_manager.po_dao.get_by_id_and_workspace = MagicMock(return_value=po)

    count_query = MagicMock()
    count_query.filter.return_value = count_query
    count_query.count.return_value = 2
    session.query.return_value = count_query

    with pytest.raises(HTTPException) as exc:
        po_manager_module.purchase_order_manager.delete_purchase_order(
            session, po_id=100, workspace_id=1
        )

    assert 'receiving history' in exc.value.detail
    mock_get_items.assert_not_called()
