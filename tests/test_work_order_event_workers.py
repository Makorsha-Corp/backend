"""Tests for work order event log worker metadata."""
from unittest.mock import MagicMock, patch

from app.managers.work_order_manager import work_order_manager
from app.models.enums import WorkOrderStatusEnum


def _minimal_wo(**overrides):
    wo = MagicMock()
    wo.id = 1
    wo.workspace_id = 10
    wo.work_order_number = 'WO-2026-001'
    wo.title = 'Test job'
    wo.status = WorkOrderStatusEnum.DRAFT.value
    wo.machine_id = None
    wo.project_component_id = None
    wo.planned_date = None
    wo.assigned_to = 'Jane Worker, Bob'
    wo.started_by = None
    wo.started_at = None
    for key, value in overrides.items():
        setattr(wo, key, value)
    return wo


@patch('app.managers.work_order_manager.work_order_assignee_dao')
@patch.object(work_order_manager, '_schedule_metadata_for_actual', return_value={})
@patch.object(work_order_manager, '_run_start_side_effects', return_value=(0, None))
@patch.object(work_order_manager, 'approvals_met', return_value=True)
@patch.object(work_order_manager, 'log_event')
@patch.object(work_order_manager, 'get_work_order')
def test_start_work_order_snapshots_worker_metadata(
    mock_get_wo,
    mock_log_event,
    _mock_approvals,
    _mock_start_effects,
    _mock_schedule_meta,
    mock_assignee_dao,
) -> None:
    session = MagicMock()
    wo = _minimal_wo()
    mock_get_wo.return_value = wo
    mock_assignee_dao.get_user_ids_by_order.return_value = [42, 43]

    work_order_manager.start_work_order(session, wo_id=1, workspace_id=10, user_id=7)

    metadata = mock_log_event.call_args.kwargs['metadata']
    assert metadata['assigned_to'] == 'Jane Worker, Bob'
    assert metadata['assignee_user_ids'] == [42, 43]
    assert metadata['started_by_user_id'] == 7


@patch.object(work_order_manager.wo_dao, 'update')
@patch.object(work_order_manager, '_sync_assignees_from_text', return_value=[99])
@patch.object(work_order_manager, '_collect_field_changes')
@patch.object(work_order_manager, 'log_event')
@patch.object(work_order_manager.wo_dao, 'get_by_id_and_workspace')
@patch.object(work_order_manager, '_is_locked', return_value=False)
def test_update_work_order_emits_workers_updated_event(
    _mock_locked,
    mock_get_by_id,
    mock_log_event,
    mock_collect_changes,
    _mock_sync,
    _mock_update,
) -> None:
    session = MagicMock()
    wo = _minimal_wo(assigned_to='Jane Worker')
    wo.is_deleted = False
    mock_get_by_id.return_value = wo
    mock_collect_changes.return_value = [
        {
            'field': 'assigned_to',
            'label': 'Assigned to',
            'from_value': 'Jane Worker',
            'to_value': 'Bob Contractor',
        },
    ]

    from app.schemas.work_order import WorkOrderUpdate

    work_order_manager.update_work_order(
        session, wo_id=1, data=WorkOrderUpdate(assigned_to='Bob Contractor'),
        workspace_id=10, user_id=7,
    )

    event_types = [call.args[3] for call in mock_log_event.call_args_list]
    assert 'workers_updated' in event_types
    workers_call = next(call for call in mock_log_event.call_args_list if call.args[3] == 'workers_updated')
    metadata = workers_call.kwargs['metadata']
    assert metadata['from_value'] == 'Jane Worker'
    assert metadata['to_value'] == 'Bob Contractor'
    assert metadata['assignee_user_ids'] == [99]
