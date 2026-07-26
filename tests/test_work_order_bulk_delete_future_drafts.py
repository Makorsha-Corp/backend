"""Tests for bulk delete of future recurring program drafts."""
from datetime import date
from unittest.mock import MagicMock, patch

from app.managers.work_order_manager import work_order_manager
from app.models.enums import WorkOrderStatusEnum


@patch.object(work_order_manager.wo_dao, 'soft_delete')
@patch.object(work_order_manager.wo_dao, 'list_future_drafts_for_template_machine')
def test_bulk_delete_future_recurrence_drafts_soft_deletes_matches(
    mock_list: MagicMock,
    mock_soft_delete: MagicMock,
) -> None:
    session = MagicMock()
    wo1 = MagicMock(id=10, status=WorkOrderStatusEnum.DRAFT.value)
    wo2 = MagicMock(id=11, status=WorkOrderStatusEnum.DRAFT.value)
    mock_list.return_value = [wo1, wo2]
    mock_soft_delete.side_effect = lambda session, *, db_obj, deleted_by: db_obj

    deleted_ids = work_order_manager.bulk_delete_future_recurrence_drafts(
        session,
        workspace_id=1,
        user_id=7,
        work_order_template_id=3,
        machine_id=5,
        after_date=date.today(),
    )

    mock_list.assert_called_once()
    assert mock_soft_delete.call_count == 2
    assert deleted_ids == [10, 11]


@patch.object(work_order_manager.wo_dao, 'list_future_drafts_for_template_machine')
def test_bulk_delete_future_recurrence_drafts_empty(mock_list: MagicMock) -> None:
    session = MagicMock()
    mock_list.return_value = []

    deleted_ids = work_order_manager.bulk_delete_future_recurrence_drafts(
        session,
        workspace_id=1,
        user_id=7,
        work_order_template_id=3,
        machine_id=5,
        after_date=date.today(),
    )

    assert deleted_ids == []


def test_bulk_delete_future_drafts_route_registered() -> None:
    from app.main import app

    paths = app.openapi()["paths"]
    assert "/api/v1/work-orders/bulk-delete-future-drafts/" in paths
    assert "post" in paths["/api/v1/work-orders/bulk-delete-future-drafts/"]
