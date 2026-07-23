"""Unit tests for work order schedule staging with optional factory sections."""
from datetime import date
from unittest.mock import MagicMock, patch

from app.main import app  # noqa: F401 — ensures app package is importable in tests
from app.managers.work_order_schedule_manager import work_order_schedule_manager
from app.models.enums import WorkOrderPriorityEnum
from app.schemas.work_order_schedule import StageWorkOrderDayRequest


def _make_machine(*, mid: int, factory_id: int, section_id=None, name: str = "M1"):
    machine = MagicMock()
    machine.id = mid
    machine.factory_id = factory_id
    machine.factory_section_id = section_id
    machine.name = name
    return machine


def _make_template(*, tpl_id: int = 1, type_id: int = 10):
    tpl = MagicMock()
    tpl.id = tpl_id
    tpl.default_machine_id = None
    tpl.default_factory_section_id = None
    tpl.work_order_type_id = type_id
    tpl.work_order_type_name = "Maintenance"
    tpl.description = None
    tpl.priority = WorkOrderPriorityEnum.MEDIUM
    tpl.assigned_to = None
    tpl.is_recurring = True
    tpl.next_generation_date = date(2026, 7, 17)
    tpl.recurrence_type = "daily"
    tpl.recurrence_day = None
    tpl.generation_mode = "schedule"
    return tpl


@patch("app.managers.work_order_schedule_manager.machine_dao")
@patch("app.utils.work_order_generation.machine_dao")
@patch("app.managers.work_order_schedule_manager.work_order_schedule_dao")
@patch("app.managers.work_order_schedule_manager.work_order_dao")
@patch("app.managers.work_order_schedule_manager.work_order_template_dao")
def test_stage_day_factory_only_includes_unassigned_machines(
    mock_tpl_dao,
    mock_wo_dao,
    mock_schedule_dao,
    mock_gen_machine_dao,
    mock_manager_machine_dao,
) -> None:
    session = MagicMock()
    tpl = _make_template()
    mock_tpl_dao.list_recurring_due.return_value = [tpl]

    unassigned = _make_machine(mid=5, factory_id=1, section_id=None)
    mock_gen_machine_dao.get_by_factory.return_value = [unassigned]
    mock_manager_machine_dao.get_by_id_and_workspace.return_value = unassigned
    mock_schedule_dao.find_staged.return_value = None
    mock_wo_dao.get_by_machine_date_type.return_value = None

    body = StageWorkOrderDayRequest(target_date=date(2026, 7, 17), factory_id=1)
    created = work_order_schedule_manager.stage_day(
        session,
        body=body,
        workspace_id=1,
        user_id=1,
    )

    mock_gen_machine_dao.get_by_factory.assert_called_once_with(
        session, factory_id=1, workspace_id=1, limit=1000,
    )
    assert len(created) == 1
    assert created[0].machine_id == 5
    assert created[0].factory_id == 1
    assert created[0].factory_section_id is None


@patch("app.managers.work_order_schedule_manager.machine_dao")
@patch("app.utils.work_order_generation.machine_dao")
@patch("app.managers.work_order_schedule_manager.work_order_schedule_dao")
@patch("app.managers.work_order_schedule_manager.work_order_dao")
@patch("app.managers.work_order_schedule_manager.work_order_template_dao")
def test_stage_day_default_machine_without_section_does_not_error(
    mock_tpl_dao,
    mock_wo_dao,
    mock_schedule_dao,
    mock_gen_machine_dao,
    mock_manager_machine_dao,
) -> None:
    session = MagicMock()
    tpl = _make_template()
    tpl.default_machine_id = 9
    mock_tpl_dao.list_recurring_due.return_value = [tpl]

    machine = _make_machine(mid=9, factory_id=2, section_id=None, name="Unassigned")
    mock_manager_machine_dao.get_by_id_and_workspace.return_value = machine
    mock_schedule_dao.find_staged.return_value = None
    mock_wo_dao.get_by_machine_date_type.return_value = None

    body = StageWorkOrderDayRequest(target_date=date(2026, 7, 17), factory_id=2)
    created = work_order_schedule_manager.stage_day(
        session,
        body=body,
        workspace_id=1,
        user_id=1,
    )

    assert len(created) == 1
    assert created[0].factory_section_id is None
    mock_gen_machine_dao.get_by_factory.assert_not_called()
