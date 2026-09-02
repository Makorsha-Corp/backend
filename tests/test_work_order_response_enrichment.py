"""Tests for batched work order response enrichment."""
from unittest.mock import MagicMock, patch

from app.models.enums import WorkOrderPriorityEnum, WorkOrderStatusEnum
from app.schemas.work_order import WorkOrderResponse
from app.services.work_order_service import WorkOrderService, _WorkOrderEnrichment


def _minimal_response(**overrides) -> WorkOrderResponse:
    data = {
        'id': 1,
        'workspace_id': 10,
        'work_order_number': 'WO-2026-001',
        'work_order_type_id': 1,
        'title': 'Test job',
        'priority': WorkOrderPriorityEnum.MEDIUM,
        'status': WorkOrderStatusEnum.DRAFT,
        'factory_id': 1,
        'uses_inventory': False,
        'created_at': '2026-01-01T00:00:00Z',
        'is_active': True,
        'is_deleted': False,
    }
    data.update(overrides)
    return WorkOrderResponse.model_validate(data)


def _wo(**overrides):
    wo = MagicMock()
    wo.id = overrides.pop('id', 1)
    wo.workspace_id = overrides.pop('workspace_id', 10)
    wo.started_by = overrides.pop('started_by', None)
    wo.completed_by = overrides.pop('completed_by', None)
    wo.completed_by_names = overrides.pop('completed_by_names', None)
    for key, value in overrides.items():
        setattr(wo, key, value)
    return wo


@patch('app.services.work_order_service.work_order_completer_dao')
@patch('app.services.work_order_service.work_order_assignee_dao')
def test_load_work_order_enrichment_batches_junction_lookups(
    mock_assignee_dao,
    mock_completer_dao,
) -> None:
    service = WorkOrderService()
    db = MagicMock()
    orders = [_wo(id=1), _wo(id=2)]

    mock_assignee_dao.get_user_ids_by_orders.return_value = {1: [11], 2: [22]}
    mock_completer_dao.get_user_ids_by_orders.return_value = {1: [33], 2: []}

    enrichment = service._load_work_order_enrichment(db, orders)

    mock_assignee_dao.get_user_ids_by_orders.assert_called_once_with(
        db, work_order_ids=[1, 2], workspace_id=10,
    )
    mock_completer_dao.get_user_ids_by_orders.assert_called_once_with(
        db, work_order_ids=[1, 2], workspace_id=10,
    )
    assert enrichment.assignee_map[1] == [11]
    assert enrichment.assignee_map[2] == [22]
    assert enrichment.completer_map[1] == [33]
    assert enrichment.completer_map[2] == []


def test_to_work_order_response_applies_enrichment_maps() -> None:
    service = WorkOrderService()
    db = MagicMock()
    order = _wo(id=3, completed_by_names='Jane Worker, Bob')
    enrichment = _WorkOrderEnrichment(
        assignee_map={3: [11]},
        completer_map={3: [33]},
        profile_names={},
    )

    with patch.object(WorkOrderResponse, 'model_validate', return_value=_minimal_response(id=3)):
        response = service._to_work_order_response(db, order, enrichment=enrichment)

    assert response.assignee_user_ids == [11]
    assert response.completer_user_ids == [33]
    assert response.completed_by_name == 'Jane Worker, Bob'


def test_list_sheet_bundles_enriches_orders_in_one_batch() -> None:
    service = WorkOrderService()
    db = MagicMock()
    order = _wo(id=5)

    with patch.object(service.manager, 'count_sheet_orders', return_value=0), patch.object(
        service.manager, 'list_sheet_orders', return_value=[order],
    ), patch.object(service.manager, 'get_items', return_value=[]), patch.object(
        service.manager, 'list_approvers', return_value=[],
    ), patch.object(
        service.manager, 'approval_summary', return_value=(0, 0, False),
    ), patch.object(service, '_to_work_order_responses') as mock_to_responses:
        mock_to_responses.return_value = [_minimal_response(id=5)]
        service.list_sheet_bundles(db, workspace_id=10)
        mock_to_responses.assert_called_once_with(db, [order])
