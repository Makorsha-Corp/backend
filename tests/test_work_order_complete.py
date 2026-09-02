"""Tests for work order completion worker (completed_by) stamping."""
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.managers.work_order_manager import work_order_manager
from app.models.enums import WorkOrderStatusEnum


def _minimal_wo(**overrides):
    wo = MagicMock()
    wo.id = 1
    wo.workspace_id = 10
    wo.work_order_number = 'WO-2026-001'
    wo.title = 'Test job'
    wo.status = WorkOrderStatusEnum.IN_PROGRESS.value
    wo.machine_id = None
    wo.project_component_id = None
    wo.planned_date = None
    wo.completion_notes = None
    wo.completed_by = None
    wo.completed_by_names = None
    wo.completed_at = None
    for key, value in overrides.items():
        setattr(wo, key, value)
    return wo


@patch('app.managers.work_order_manager.work_order_completer_dao')
@patch.object(work_order_manager, 'log_event')
@patch.object(work_order_manager, '_schedule_metadata_for_actual', return_value=None)
@patch.object(work_order_manager, '_resolve_completion_workers', return_value=('Jane Worker', [42]))
def test_finalize_completion_stamps_worker_and_metadata(
    _mock_resolve,
    _mock_schedule_meta,
    mock_log_event,
    mock_completer_dao,
) -> None:
    session = MagicMock()
    wo = _minimal_wo()

    result = work_order_manager.finalize_completion(
        session, wo, performed_by_user_id=7,
        completed_by_names='Jane Worker',
        completed_by_user_ids=[42],
    )

    assert result is wo
    assert wo.completed_by_names == 'Jane Worker'
    assert wo.completed_by == 42
    assert wo.status == WorkOrderStatusEnum.COMPLETED.value
    mock_completer_dao.replace_for_order.assert_called_once()
    metadata = mock_log_event.call_args.kwargs['metadata']
    assert metadata['completed_by_names'] == 'Jane Worker'
    assert metadata['completed_by_user_ids'] == [42]
    assert metadata['recorded_by'] == 7


@patch.object(work_order_manager, '_resolve_completion_workers')
def test_finalize_completion_rejects_inactive_member(mock_resolve) -> None:
    mock_resolve.side_effect = HTTPException(
        status_code=400,
        detail='User is not an active member of this workspace',
    )
    wo = _minimal_wo()

    with pytest.raises(HTTPException) as exc:
        work_order_manager.finalize_completion(
            MagicMock(), wo, performed_by_user_id=7, completed_by_user_ids=[99],
        )
    assert exc.value.status_code == 400


@patch('app.managers.work_order_manager.work_order_completer_dao')
@patch.object(work_order_manager, 'log_event')
@patch.object(work_order_manager, '_schedule_metadata_for_actual', return_value=None)
@patch.object(work_order_manager, '_resolve_completion_workers', return_value=('Actor User', [7]))
def test_finalize_completion_defaults_worker_to_actor(
    _mock_resolve,
    _mock_schedule_meta,
    mock_log_event,
    _mock_completer_dao,
) -> None:
    session = MagicMock()
    wo = _minimal_wo()

    work_order_manager.finalize_completion(session, wo, performed_by_user_id=7)

    assert wo.completed_by == 7
    metadata = mock_log_event.call_args.kwargs['metadata']
    assert metadata['completed_by_names'] == 'Actor User'
    assert metadata['completed_by_user_ids'] == [7]
    assert 'recorded_by' not in metadata


@patch.object(work_order_manager, 'finalize_completion')
@patch.object(work_order_manager, 'log_event')
@patch.object(work_order_manager, '_run_start_side_effects')
@patch.object(work_order_manager, 'approvals_met', return_value=True)
@patch.object(work_order_manager, 'get_work_order')
def test_complete_as_planned_forwards_completion_workers(
    mock_get_wo,
    _mock_approvals,
    mock_start_effects,
    _mock_log_event,
    mock_finalize,
) -> None:
    from datetime import date, timedelta

    session = MagicMock()
    planned = date.today() - timedelta(days=3)
    wo = _minimal_wo(status=WorkOrderStatusEnum.DRAFT.value, planned_date=planned)
    mock_get_wo.return_value = wo
    mock_start_effects.return_value = (0, None)
    mock_finalize.return_value = wo

    work_order_manager.complete_as_planned(
        session, wo_id=1, workspace_id=10, user_id=7,
        completed_by_names='Jane Worker',
        completed_by_user_ids=[42],
    )

    kwargs = mock_finalize.call_args.kwargs
    assert kwargs['completed_by_names'] == 'Jane Worker'
    assert kwargs['completed_by_user_ids'] == [42]
