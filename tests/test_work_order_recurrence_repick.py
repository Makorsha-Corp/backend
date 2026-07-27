"""Tests for recurring program repick (reseed + draft sync on sheet save)."""

from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.managers.work_order_manager import work_order_manager


def _anchored_template() -> SimpleNamespace:
    return SimpleNamespace(
        id=10,
        is_recurring=True,
        recurrence_type='weekly',
        recurrence_day=None,
        recurrence_start_date=date(2026, 8, 3),
        recurrence_end_date=date(2026, 8, 31),
        next_generation_date=date(2026, 8, 10),
        work_order_type_id=3,
    )


@patch('app.managers.work_order_manager.work_order_template_manager')
def test_maybe_seed_no_op_when_anchored_range_unchanged(mock_tpl_manager) -> None:
    session = MagicMock()
    template = _anchored_template()
    mock_tpl_manager.get_template.return_value = template

    work_order_manager._maybe_seed_template_recurrence(
        session,
        template_id=10,
        workspace_id=1,
        user_id=7,
        machine_id=5,
        planned_date=date(2026, 8, 3),
        recurrence_end_date=date(2026, 8, 31),
    )

    mock_tpl_manager.generate_drafts_for_anchored_range.assert_not_called()


@patch.object(work_order_manager, 'sync_recurrence_drafts_for_machine')
@patch('app.managers.work_order_manager.work_order_template_manager')
def test_maybe_seed_reseeds_when_anchored_range_changed(
    mock_tpl_manager,
    mock_sync,
) -> None:
    session = MagicMock()
    template = _anchored_template()
    mock_tpl_manager.get_template.return_value = template

    work_order_manager._maybe_seed_template_recurrence(
        session,
        template_id=10,
        workspace_id=1,
        user_id=7,
        machine_id=5,
        planned_date=date(2026, 9, 1),
        recurrence_end_date=date(2026, 9, 30),
    )

    assert template.recurrence_start_date == date(2026, 9, 1)
    assert template.recurrence_end_date == date(2026, 9, 30)
    mock_sync.assert_called_once_with(
        session,
        workspace_id=1,
        user_id=7,
        template=template,
        machine_id=5,
        range_start=date(2026, 9, 1),
        range_end=date(2026, 9, 30),
    )


@patch('app.managers.work_order_manager.work_order_template_manager')
def test_sync_recurrence_drafts_deletes_orphans_and_generates(mock_tpl_manager) -> None:
    session = MagicMock()
    template = _anchored_template()
    orphan = SimpleNamespace(id=101)
    work_order_manager.wo_dao.list_drafts_outside_range_for_template_machine = MagicMock(
        return_value=[orphan],
    )
    work_order_manager.wo_dao.soft_delete = MagicMock()

    work_order_manager.sync_recurrence_drafts_for_machine(
        session,
        workspace_id=1,
        user_id=7,
        template=template,
        machine_id=5,
        range_start=date(2026, 8, 3),
        range_end=date(2026, 8, 17),
    )

    work_order_manager.wo_dao.soft_delete.assert_called_once_with(
        session,
        db_obj=orphan,
        deleted_by=7,
    )
    mock_tpl_manager.generate_drafts_for_anchored_range.assert_called_once_with(
        session,
        template=template,
        machine_id=5,
        workspace_id=1,
        user_id=7,
    )
