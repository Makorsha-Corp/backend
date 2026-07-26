"""Tests for auto-generating recurring draft work orders on first sheet anchor."""

from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from app.managers.work_order_template_manager import WorkOrderTemplateManager
from app.utils.work_order_recurrence import seed_recurrence_from_planned_date


def _weekly_template(*, next_due: date | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        id=10,
        is_recurring=True,
        recurrence_type='weekly',
        recurrence_day=None,
        recurrence_start_date=None,
        recurrence_end_date=None,
        next_generation_date=next_due,
        work_order_type_id=3,
    )


@patch('app.managers.work_order_manager.work_order_manager')
def test_generate_drafts_for_anchored_range_weekly(mock_wo_manager) -> None:
    session = MagicMock()
    template = _weekly_template()
    seed_recurrence_from_planned_date(template, date(2026, 1, 15), date(2026, 2, 15))

    mock_wo_manager.wo_dao.get_by_machine_date_type.return_value = None
    created_wos = []
    mock_wo_manager.create_work_order_from_template.side_effect = (
        lambda *args, **kwargs: SimpleNamespace(
            id=len(created_wos) + 100,
            planned_date=kwargs['overrides'].planned_date,
        )
    )

    manager = WorkOrderTemplateManager()
    created = manager.generate_drafts_for_anchored_range(
        session,
        template=template,
        machine_id=5,
        workspace_id=1,
        user_id=7,
    )

    assert len(created) == 4
    assert [wo.planned_date for wo in created] == [
        date(2026, 1, 22),
        date(2026, 1, 29),
        date(2026, 2, 5),
        date(2026, 2, 12),
    ]
    assert template.next_generation_date == date(2026, 2, 19)
    assert mock_wo_manager.create_work_order_from_template.call_count == 4


@patch('app.managers.work_order_manager.work_order_manager')
def test_generate_drafts_skips_existing_on_date(mock_wo_manager) -> None:
    session = MagicMock()
    template = _weekly_template(next_due=date(2026, 1, 22))
    template.recurrence_end_date = date(2026, 2, 15)

    existing = SimpleNamespace(id=99)

    def lookup(*_args, **kwargs):
        if kwargs.get('planned_date') == date(2026, 1, 29):
            return existing
        return None

    mock_wo_manager.wo_dao.get_by_machine_date_type.side_effect = lookup
    mock_wo_manager.create_work_order_from_template.side_effect = (
        lambda *args, **kwargs: SimpleNamespace(
            id=200,
            planned_date=kwargs['overrides'].planned_date,
        )
    )

    manager = WorkOrderTemplateManager()
    created = manager.generate_drafts_for_anchored_range(
        session,
        template=template,
        machine_id=5,
        workspace_id=1,
        user_id=7,
    )

    planned_dates = {wo.planned_date for wo in created}
    assert date(2026, 1, 29) not in planned_dates
    assert mock_wo_manager.create_work_order_from_template.call_count == 3
