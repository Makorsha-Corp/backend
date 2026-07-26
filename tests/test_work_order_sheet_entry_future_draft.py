"""Tests for future-dated sheet entry creating draft work orders."""
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from app.managers.work_order_manager import work_order_manager
from app.models.enums import WorkOrderStatusEnum
from app.schemas.work_order import WorkOrderSheetEntryCreate, WorkOrderSheetItemLine


def _future_date() -> date:
    return date.today() + timedelta(days=7)


@patch('app.managers.work_order_manager.work_order_type_dao')
@patch('app.managers.work_order_manager.machine_dao')
@patch.object(work_order_manager, 'create_work_order')
def test_future_sheet_entry_creates_draft_work_order(
    mock_create_wo,
    mock_machine_dao,
    mock_type_dao,
) -> None:
    session = MagicMock()
    machine = MagicMock()
    machine.id = 5
    machine.factory_id = 1
    machine.factory_section_id = None
    machine.name = 'Loom 1'
    mock_machine_dao.get_by_id_and_workspace.return_value = machine

    wo_type = MagicMock()
    wo_type.name = 'Maintenance'
    mock_type_dao.get_by_id_and_workspace.return_value = wo_type

    work_order_manager.wo_dao.get_by_machine_date_type = MagicMock(return_value=None)

    planned = _future_date()
    wo = MagicMock()
    wo.status = WorkOrderStatusEnum.DRAFT.value
    wo.planned_date = planned
    mock_create_wo.return_value = wo

    data = WorkOrderSheetEntryCreate(
        machine_id=5,
        work_order_type_id=10,
        planned_date=planned,
        description='Check belts',
        items=[WorkOrderSheetItemLine(item_id=99, quantity=Decimal('2'))],
    )

    record = work_order_manager.sheet_entry(session, data=data, workspace_id=1, user_id=7)

    mock_create_wo.assert_called_once()
    assert record is wo


@patch('app.managers.work_order_manager.work_order_type_dao')
@patch('app.managers.work_order_manager.machine_dao')
def test_future_sheet_entry_merges_into_existing_draft(
    mock_machine_dao,
    mock_type_dao,
) -> None:
    session = MagicMock()
    machine = MagicMock()
    machine.id = 5
    machine.factory_id = 1
    machine.factory_section_id = None
    machine.name = 'Loom 1'
    mock_machine_dao.get_by_id_and_workspace.return_value = machine
    mock_type_dao.get_by_id_and_workspace.return_value = MagicMock(name='Maintenance')

    existing = MagicMock()
    existing.id = 42
    existing.status = WorkOrderStatusEnum.DRAFT.value
    work_order_manager.wo_dao.get_by_machine_date_type = MagicMock(return_value=existing)

    with patch.object(work_order_manager, '_apply_sheet_entry_lines') as mock_apply:
        data = WorkOrderSheetEntryCreate(
            machine_id=5,
            work_order_type_id=10,
            planned_date=_future_date(),
            description='Extra note',
        )
        record = work_order_manager.sheet_entry(session, data=data, workspace_id=1, user_id=7)

    assert record is existing
    mock_apply.assert_not_called()
