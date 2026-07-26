"""Unit tests for machine upcoming work helper."""
from datetime import date
from unittest.mock import MagicMock, patch

from app.services.machine_work_service import machine_work_service


def _make_machine(*, mid: int = 1, name: str = "Loom 1", factory_id: int = 10, section_id=None):
    machine = MagicMock()
    machine.id = mid
    machine.name = name
    machine.factory_id = factory_id
    machine.factory_section_id = section_id
    machine.factory_section_name = "Weaving" if section_id else None
    machine.is_deleted = False
    return machine


def _make_work_order(*, wid: int, machine_id: int, planned_date: date, title: str = "Inspect"):
    wo = MagicMock()
    wo.id = wid
    wo.machine_id = machine_id
    wo.planned_date = planned_date
    wo.title = title
    wo.work_order_number = f"WO-{wid}"
    wo.status = "DRAFT"
    wo.work_order_type_name = "Maintenance"
    return wo


@patch.object(machine_work_service, "collect_raw_items")
def test_upcoming_work_aggregates_by_machine(mock_collect) -> None:
    machine = _make_machine()
    wo1 = _make_work_order(wid=1, machine_id=1, planned_date=date(2026, 7, 26))
    wo2 = _make_work_order(wid=2, machine_id=1, planned_date=date(2026, 7, 28))
    mock_collect.return_value = [(wo1, machine), (wo2, machine)]

    rows = machine_work_service.upcoming_work(
        db=MagicMock(),
        workspace_id=1,
        start=date(2026, 7, 24),
        end=date(2026, 7, 31),
    )

    assert len(rows) == 1
    row = rows[0]
    assert row.machine_id == 1
    assert row.count == 2
    assert row.sources.work_orders == 2
    assert row.earliest_date == date(2026, 7, 26)


@patch.object(machine_work_service, "collect_raw_items")
def test_upcoming_work_returns_multiple_machines(mock_collect) -> None:
    m1 = _make_machine(mid=1, name="A")
    m2 = _make_machine(mid=2, name="B")
    wo1 = _make_work_order(wid=1, machine_id=1, planned_date=date(2026, 7, 25))
    wo2 = _make_work_order(wid=2, machine_id=2, planned_date=date(2026, 7, 27))
    mock_collect.return_value = [(wo1, m1), (wo2, m2)]

    rows = machine_work_service.upcoming_work(
        db=MagicMock(),
        workspace_id=1,
        start=date(2026, 7, 24),
        end=date(2026, 7, 31),
    )

    assert [r.machine_id for r in rows] == [1, 2]


@patch.object(machine_work_service, "collect_raw_items")
def test_dates_by_machine_collects_all_dates(mock_collect) -> None:
    machine = _make_machine()
    overdue = _make_work_order(wid=1, machine_id=1, planned_date=date(2026, 7, 20))
    upcoming = _make_work_order(wid=2, machine_id=1, planned_date=date(2026, 7, 26))
    mock_collect.return_value = [(overdue, machine), (upcoming, machine)]

    result = machine_work_service.dates_by_machine(
        db=MagicMock(),
        workspace_id=1,
        machine_ids=[1],
        start=date(2026, 1, 1),
        end=date(2026, 12, 31),
    )

    assert result[1] == [date(2026, 7, 20), date(2026, 7, 26)]
    assert machine_work_service.has_overdue(result[1], date(2026, 7, 24))
    assert machine_work_service.earliest_upcoming_on_or_after(result[1], date(2026, 7, 24)) == date(
        2026, 7, 26
    )
