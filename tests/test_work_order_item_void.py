"""Tests for work order item void (soft delete) and mixed action types."""
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.managers.work_order_manager import work_order_manager
from app.models.enums import WorkOrderStatusEnum
from app.schemas.work_order_item import WorkOrderItemCreate


def _make_wo(status: str = WorkOrderStatusEnum.DRAFT.value) -> MagicMock:
    wo = MagicMock()
    wo.id = 10
    wo.workspace_id = 1
    wo.status = status
    wo.machine_id = 5
    wo.work_order_number = 'WO-2026-001'
    wo.uses_inventory = True
    return wo


def _make_item(
    *,
    item_id: int = 99,
    action_type: str = 'CONSUME',
    consumed_at=None,
    is_deleted: bool = False,
) -> MagicMock:
    item = MagicMock()
    item.id = item_id
    item.work_order_id = 10
    item.workspace_id = 1
    item.item_id = item_id
    item.quantity = Decimal('2')
    item.uses_inventory = True
    item.source_location_type = 'storage'
    item.source_location_id = 1
    item.action_type = action_type
    item.replaced_item_id = None
    item.consumed_at = consumed_at
    item.consumed_by = 7 if consumed_at else None
    item.unit_cost = Decimal('10') if consumed_at else None
    item.total_cost = Decimal('20') if consumed_at else None
    item.is_deleted = is_deleted
    return item


@patch('app.managers.work_order_manager.item_name', return_value='Belt')
@patch.object(work_order_manager, 'log_event')
@patch.object(work_order_manager, '_has_recorded_approvals', return_value=False)
@patch.object(work_order_manager, 'get_work_order')
@patch.object(work_order_manager.item_dao, 'get_by_id_and_workspace')
def test_remove_draft_item_soft_deletes(
    mock_get_item,
    mock_get_wo,
    _mock_approvals,
    mock_log,
    _mock_name,
) -> None:
    session = MagicMock()
    item = _make_item()
    mock_get_item.return_value = item
    mock_get_wo.return_value = _make_wo(WorkOrderStatusEnum.DRAFT.value)

    result = work_order_manager.remove_item(session, item_id=99, workspace_id=1, user_id=7)

    assert result is item
    assert item.is_deleted is True
    assert item.deleted_by == 7
    assert item.deleted_at is not None
    session.flush.assert_called()
    mock_log.assert_called_once()
    assert mock_log.call_args[0][3] == 'item_removed'


@patch('app.managers.work_order_manager.item_name', return_value='Motor')
@patch.object(work_order_manager, 'log_event')
@patch.object(work_order_manager, '_reverse_item_consumption')
@patch.object(work_order_manager, 'get_work_order')
@patch.object(work_order_manager.item_dao, 'get_by_id_and_workspace')
def test_remove_in_progress_consumed_item_reverses_and_soft_deletes(
    mock_get_item,
    mock_get_wo,
    mock_reverse,
    mock_log,
    _mock_name,
) -> None:
    session = MagicMock()
    item = _make_item(consumed_at=datetime.utcnow())
    mock_get_item.return_value = item
    mock_get_wo.return_value = _make_wo(WorkOrderStatusEnum.IN_PROGRESS.value)

    work_order_manager.remove_item(session, item_id=99, workspace_id=1, user_id=7)

    mock_reverse.assert_called_once_with(session, mock_get_wo.return_value, item, 7)
    assert item.is_deleted is True
    assert mock_log.call_args[0][3] == 'item_voided'


@patch.object(work_order_manager, 'get_work_order')
@patch.object(work_order_manager.item_dao, 'get_by_id_and_workspace')
def test_remove_completed_item_rejected(mock_get_item, mock_get_wo) -> None:
    session = MagicMock()
    item = _make_item(consumed_at=datetime.utcnow())
    mock_get_item.return_value = item
    mock_get_wo.return_value = _make_wo(WorkOrderStatusEnum.COMPLETED.value)

    with pytest.raises(HTTPException) as exc:
        work_order_manager.remove_item(session, item_id=99, workspace_id=1, user_id=7)

    assert exc.value.status_code == 400


@patch.object(work_order_manager.item_dao, 'get_by_work_order')
def test_duplicate_check_ignores_soft_deleted_lines(mock_get_by_wo) -> None:
    session = MagicMock()
    active = _make_item(item_id=50)
    active.is_deleted = False
    deleted = _make_item(item_id=50)
    deleted.id = 51
    deleted.is_deleted = True
    mock_get_by_wo.return_value = [active]

    # Should not raise — only active line counts
    work_order_manager._ensure_catalog_item_not_on_wo(session, 10, 60, 1)

    with pytest.raises(HTTPException) as exc:
        work_order_manager._ensure_catalog_item_not_on_wo(session, 10, 50, 1)
    assert exc.value.status_code == 409


@patch('app.managers.work_order_manager.item_name', return_value='Motor')
@patch.object(work_order_manager.item_dao, 'create')
@patch.object(work_order_manager, '_ensure_catalog_item_not_on_wo')
@patch.object(work_order_manager, 'log_event')
@patch.object(work_order_manager, '_guard_item_mutations')
@patch.object(work_order_manager, 'get_work_order')
def test_add_item_persists_per_line_action_type(
    mock_get_wo,
    _mock_guard,
    _mock_log,
    _mock_dup,
    mock_create,
    _mock_name,
) -> None:
    session = MagicMock()
    mock_get_wo.return_value = _make_wo()
    created = MagicMock()
    created.action_type = 'INSTALL'
    created.item_id = 1
    created.quantity = Decimal('1')
    mock_create.return_value = created

    data = WorkOrderItemCreate(
        work_order_id=10,
        item_id=1,
        quantity=Decimal('1'),
        uses_inventory=True,
        source_location_type='storage',
        source_location_id=1,
        action_type='INSTALL',
    )
    result = work_order_manager.add_item(session, data, workspace_id=1, user_id=7)
    assert result.action_type == 'INSTALL'
    create_payload = mock_create.call_args[1]['obj_in']
    assert create_payload['action_type'] == 'INSTALL'


@patch('app.managers.work_order_manager.post_stock_in')
@patch('app.managers.work_order_manager.item_name', return_value='Belt')
@patch.object(work_order_manager, 'log_event')
@patch.object(work_order_manager.item_dao, 'update')
@patch.object(work_order_manager, 'get_work_order')
@patch.object(work_order_manager.item_dao, 'get_by_id_and_workspace')
def test_update_consumed_item_decrease_returns_stock(
    mock_get_item,
    mock_get_wo,
    mock_update,
    mock_log,
    _mock_name,
    mock_stock_in,
) -> None:
    session = MagicMock()
    item = _make_item(consumed_at=datetime.utcnow())
    mock_get_item.return_value = item
    mock_get_wo.return_value = _make_wo(WorkOrderStatusEnum.IN_PROGRESS.value)
    updated = _make_item(consumed_at=datetime.utcnow())
    updated.quantity = Decimal('1')
    mock_update.return_value = updated

    from app.schemas.work_order_item import WorkOrderItemUpdate

    work_order_manager.update_item(
        session,
        item_id=99,
        data=WorkOrderItemUpdate(quantity=Decimal('1')),
        workspace_id=1,
        user_id=7,
    )

    mock_stock_in.assert_called_once()
    assert mock_stock_in.call_args[1]['qty'] == 1
    assert mock_log.call_args[0][3] == 'item_quantity_adjusted'


@patch('app.managers.work_order_manager.post_stock_out', return_value=Decimal('5'))
@patch('app.managers.work_order_manager.item_name', return_value='Belt')
@patch.object(work_order_manager, 'log_event')
@patch.object(work_order_manager.item_dao, 'update')
@patch.object(work_order_manager, 'get_work_order')
@patch.object(work_order_manager.item_dao, 'get_by_id_and_workspace')
def test_update_consumed_item_increase_deducts_stock(
    mock_get_item,
    mock_get_wo,
    mock_update,
    mock_log,
    _mock_name,
    mock_stock_out,
) -> None:
    session = MagicMock()
    item = _make_item(consumed_at=datetime.utcnow())
    mock_get_item.return_value = item
    mock_get_wo.return_value = _make_wo(WorkOrderStatusEnum.IN_PROGRESS.value)
    updated = _make_item(consumed_at=datetime.utcnow())
    updated.quantity = Decimal('3')
    mock_update.return_value = updated

    from app.schemas.work_order_item import WorkOrderItemUpdate

    work_order_manager.update_item(
        session,
        item_id=99,
        data=WorkOrderItemUpdate(quantity=Decimal('3')),
        workspace_id=1,
        user_id=7,
    )

    mock_stock_out.assert_called_once()
    assert mock_stock_out.call_args[1]['qty'] == 1
    assert mock_log.call_args[0][3] == 'item_quantity_adjusted'
