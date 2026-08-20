"""Tests for complete-as-planned retrospective work logging."""
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.managers.work_order_manager import work_order_manager
from app.models.enums import WorkOrderStatusEnum, MachineEventTypeEnum


def _past_date() -> date:
    return date.today() - timedelta(days=3)


def _future_date() -> date:
    return date.today() + timedelta(days=3)


@patch.object(work_order_manager, 'finalize_completion')
@patch.object(work_order_manager, 'log_event')
@patch.object(work_order_manager, '_run_start_side_effects')
@patch.object(work_order_manager, 'approvals_met', return_value=True)
@patch.object(work_order_manager, 'get_work_order')
def test_complete_as_planned_applies_off_machine_status(
    mock_get_wo,
    _mock_approvals,
    mock_start_effects,
    mock_log_event,
    mock_finalize,
) -> None:
    session = MagicMock()
    planned = _past_date()
    wo = MagicMock()
    wo.id = 11
    wo.status = WorkOrderStatusEnum.DRAFT.value
    wo.planned_date = planned
    wo.work_order_number = 'WO-2026-002'
    mock_get_wo.return_value = wo
    mock_start_effects.return_value = (0, None)
    mock_finalize.return_value = wo

    result = work_order_manager.complete_as_planned(
        session, wo_id=11, workspace_id=1, user_id=7,
        machine_status=MachineEventTypeEnum.OFF,
    )

    assert result is wo
    mock_finalize.assert_called_once()
    assert mock_finalize.call_args.kwargs['machine_status'] == MachineEventTypeEnum.OFF


@patch.object(work_order_manager, 'finalize_completion')
@patch.object(work_order_manager, 'log_event')
@patch.object(work_order_manager, '_run_start_side_effects')
@patch.object(work_order_manager, 'approvals_met', return_value=True)
@patch.object(work_order_manager, 'get_work_order')
def test_complete_as_planned_happy_path(
    mock_get_wo,
    _mock_approvals,
    mock_start_effects,
    mock_log_event,
    mock_finalize,
) -> None:
    session = MagicMock()
    planned = _past_date()
    wo = MagicMock()
    wo.id = 10
    wo.status = WorkOrderStatusEnum.DRAFT.value
    wo.planned_date = planned
    wo.work_order_number = 'WO-2026-001'
    mock_get_wo.return_value = wo
    mock_start_effects.return_value = (0, None)
    mock_finalize.return_value = wo

    result = work_order_manager.complete_as_planned(
        session, wo_id=10, workspace_id=1, user_id=7,
        machine_status=MachineEventTypeEnum.IDLE,
    )

    assert result is wo
    mock_start_effects.assert_called_once()
    assert wo.started_by == 7
    assert wo.started_at == datetime(planned.year, planned.month, planned.day, 12, 0, 0)
    mock_log_event.assert_called_once()
    started_meta = mock_log_event.call_args.kwargs['metadata']
    assert started_meta['completion_mode'] == 'complete_as_planned'
    mock_finalize.assert_called_once()
    finalize_kwargs = mock_finalize.call_args.kwargs
    assert finalize_kwargs['completed_at'] == wo.started_at
    assert finalize_kwargs['event_metadata_extra'] == {'completion_mode': 'complete_as_planned'}


@patch.object(work_order_manager, 'get_work_order')
def test_complete_as_planned_rejects_in_progress(mock_get_wo) -> None:
    wo = MagicMock()
    wo.status = WorkOrderStatusEnum.IN_PROGRESS.value
    wo.planned_date = _past_date()
    mock_get_wo.return_value = wo

    with pytest.raises(HTTPException) as exc:
        work_order_manager.complete_as_planned(
            MagicMock(), wo_id=1, workspace_id=1, user_id=1,
        )
    assert exc.value.status_code == 400
    assert 'draft' in exc.value.detail.lower()


@patch.object(work_order_manager, 'get_work_order')
def test_complete_as_planned_rejects_future_planned_date(mock_get_wo) -> None:
    wo = MagicMock()
    wo.status = WorkOrderStatusEnum.DRAFT.value
    wo.planned_date = _future_date()
    mock_get_wo.return_value = wo

    with pytest.raises(HTTPException) as exc:
        work_order_manager.complete_as_planned(
            MagicMock(), wo_id=1, workspace_id=1, user_id=1,
        )
    assert exc.value.status_code == 400
    assert 'planned date' in exc.value.detail.lower()


@patch.object(work_order_manager, 'approvals_met', return_value=False)
@patch.object(work_order_manager, 'get_work_order')
def test_complete_as_planned_requires_approvals(mock_get_wo, _mock_approvals) -> None:
    wo = MagicMock()
    wo.status = WorkOrderStatusEnum.DRAFT.value
    wo.planned_date = _past_date()
    mock_get_wo.return_value = wo

    with pytest.raises(HTTPException) as exc:
        work_order_manager.complete_as_planned(
            MagicMock(), wo_id=1, workspace_id=1, user_id=1,
        )
    assert exc.value.status_code == 400
    assert 'approve' in exc.value.detail.lower()


def test_planned_date_noon_utc() -> None:
    assert work_order_manager._planned_date_noon_utc(date(2026, 7, 20)) == datetime(2026, 7, 20, 12, 0, 0)


def test_variance_on_planned_noon_is_on_time() -> None:
    planned = date(2026, 7, 20)
    actual = datetime(2026, 7, 20, 12, 0, 0)
    result = work_order_manager._variance_vs_planned(planned, actual)
    assert result is not None
    assert result['variance_days'] == 0
    assert result['variance_label'] == 'On plan'
