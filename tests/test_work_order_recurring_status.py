"""Work order RECURRING pre-start status (program occurrences)."""
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.managers.work_order_manager import work_order_manager
from app.models.enums import WorkOrderStatusEnum


def test_is_pre_start_includes_recurring() -> None:
    assert work_order_manager._is_pre_start(WorkOrderStatusEnum.DRAFT.value)
    assert work_order_manager._is_pre_start(WorkOrderStatusEnum.RECURRING.value)
    assert not work_order_manager._is_pre_start(WorkOrderStatusEnum.IN_PROGRESS.value)


@patch.object(work_order_manager, '_run_start_side_effects')
@patch.object(work_order_manager, 'approvals_met', return_value=True)
@patch.object(work_order_manager, 'get_work_order')
def test_start_work_order_from_recurring(
    mock_get_wo,
    _mock_approvals,
    mock_start_effects,
) -> None:
    session = MagicMock()
    wo = MagicMock()
    wo.id = 3
    wo.status = WorkOrderStatusEnum.RECURRING.value
    wo.planned_date = date.today()
    mock_get_wo.return_value = wo
    mock_start_effects.return_value = (0, None)

    result = work_order_manager.start_work_order(session, wo_id=3, workspace_id=1, user_id=5)

    assert result.status == WorkOrderStatusEnum.IN_PROGRESS.value
    assert wo.started_by == 5


@patch.object(work_order_manager, 'finalize_completion')
@patch.object(work_order_manager, 'log_event')
@patch.object(work_order_manager, '_run_start_side_effects')
@patch.object(work_order_manager, 'approvals_met', return_value=True)
@patch.object(work_order_manager, 'get_work_order')
def test_complete_as_planned_from_recurring(
    mock_get_wo,
    _mock_approvals,
    mock_start_effects,
    _mock_log,
    mock_finalize,
) -> None:
    session = MagicMock()
    planned = date.today() - timedelta(days=2)
    wo = MagicMock()
    wo.id = 4
    wo.status = WorkOrderStatusEnum.RECURRING.value
    wo.planned_date = planned
    wo.work_order_number = 'WO-2026-010'
    mock_get_wo.return_value = wo
    mock_start_effects.return_value = (0, None)
    mock_finalize.return_value = wo

    result = work_order_manager.complete_as_planned(
        session, wo_id=4, workspace_id=1, user_id=7,
    )

    assert result is wo
    mock_finalize.assert_called_once()


def test_stop_program_deletes_future_recurring() -> None:
    from app.models.work_order_program import WorkOrderProgram

    session = MagicMock()
    program = WorkOrderProgram(id=9, workspace_id=1, status='active')
    future_recurring = MagicMock(
        id=20,
        status=WorkOrderStatusEnum.RECURRING.value,
        planned_date=date.today() + timedelta(days=7),
    )
    mock_wo_dao = MagicMock()
    mock_wo_dao.list_future_drafts_for_program.return_value = [future_recurring]

    with (
        patch.object(work_order_manager, 'wo_dao', mock_wo_dao),
        patch(
            'app.managers.work_order_manager.work_order_program_dao',
        ) as mock_program_dao,
    ):
        mock_program_dao.get_by_id_and_workspace.return_value = program
        work_order_manager.stop_work_order_program(
            session, program_id=9, workspace_id=1, user_id=1,
        )

    mock_wo_dao.soft_delete.assert_called_once_with(
        session, db_obj=future_recurring, deleted_by=1,
    )


@patch.object(work_order_manager, 'create_work_order')
def test_create_sheet_draft_with_program_uses_recurring_status(mock_create) -> None:
    mock_create.return_value = MagicMock(id=1, program_id=5)
    session = MagicMock()
    data = MagicMock()
    data.machine_id = 1
    data.work_order_type_id = 2
    data.items = []
    data.approvers = []
    data.template_id = None
    data.shift_id = None
    data.planned_start_time = None
    data.expected_duration_minutes = None
    data.description = None
    data.priority = 'MEDIUM'
    data.assigned_to = None
    data.account_id = None
    data.cost = None

    with (
        patch('app.managers.work_order_manager.machine_dao') as machine_dao,
        patch('app.managers.work_order_manager.work_order_type_dao') as type_dao,
    ):
        machine_dao.get_by_id_and_workspace.return_value = MagicMock(factory_id=3)
        type_dao.get_by_id_and_workspace.return_value = MagicMock(name='Oil change')

        work_order_manager._create_sheet_draft(
            session,
            data,
            workspace_id=1,
            user_id=2,
            planned_date=date(2026, 10, 5),
            program_id=5,
        )

    assert mock_create.call_args.kwargs['initial_status'] == WorkOrderStatusEnum.RECURRING


@patch.object(work_order_manager, 'create_work_order')
def test_create_sheet_draft_without_program_stays_draft(mock_create) -> None:
    mock_create.return_value = MagicMock(id=2)
    session = MagicMock()
    data = MagicMock()
    data.machine_id = 1
    data.work_order_type_id = 2
    data.items = []
    data.approvers = []
    data.template_id = None
    data.shift_id = None
    data.planned_start_time = None
    data.expected_duration_minutes = None
    data.description = None
    data.priority = 'MEDIUM'
    data.assigned_to = None
    data.account_id = None
    data.cost = None

    with (
        patch('app.managers.work_order_manager.machine_dao') as machine_dao,
        patch('app.managers.work_order_manager.work_order_type_dao') as type_dao,
    ):
        machine_dao.get_by_id_and_workspace.return_value = MagicMock(factory_id=3)
        type_dao.get_by_id_and_workspace.return_value = MagicMock(name='Oil change')

        work_order_manager._create_sheet_draft(
            session,
            data,
            workspace_id=1,
            user_id=2,
            planned_date=date(2026, 10, 5),
            program_id=None,
        )

    assert mock_create.call_args.kwargs.get('initial_status') is None
