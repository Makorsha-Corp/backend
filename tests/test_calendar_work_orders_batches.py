"""Unit tests for calendar work-order and production-batch chip rules."""

from datetime import date, datetime

from app.services.calendar_service import (
    build_production_batch_calendar_link,
    build_work_order_calendar_link,
    production_batch_date_chip_specs,
    work_order_date_chip_specs,
)


def test_work_order_planned_only() -> None:
    specs = work_order_date_chip_specs(date(2026, 3, 10), None)
    assert len(specs) == 1
    assert specs[0] == ("planned_date", "Planned date", date(2026, 3, 10))


def test_work_order_end_only() -> None:
    specs = work_order_date_chip_specs(None, date(2026, 3, 12))
    assert len(specs) == 1
    assert specs[0] == ("end_date", "End date", date(2026, 3, 12))


def test_work_order_same_day_planned_and_end() -> None:
    d = date(2026, 3, 10)
    specs = work_order_date_chip_specs(d, d)
    assert len(specs) == 1
    assert specs[0][0] == "planned_date"


def test_work_order_two_distinct_days() -> None:
    specs = work_order_date_chip_specs(date(2026, 3, 10), date(2026, 3, 15))
    assert len(specs) == 2
    assert specs[0][0] == "planned_date"
    assert specs[1] == ("end_date", "End date", date(2026, 3, 15))


def test_work_order_link_contains_order_id_and_scope() -> None:
    link = build_work_order_calendar_link(42, factory_id=3, machine_id=7)
    assert "orderId=42" in link
    assert "tab=workOrders" in link
    assert "factoryId=3" in link
    assert "woMachine=7" in link
    assert link.startswith("/machines?")


def test_batch_planned_start_only() -> None:
    specs = production_batch_date_chip_specs(
        date(2026, 4, 1),
        datetime(2026, 4, 2, 9, 0),
        None,
    )
    assert len(specs) == 1
    assert specs[0] == ("planned_start", "Planned start", date(2026, 4, 2))


def test_batch_batch_date_when_no_planned_start() -> None:
    specs = production_batch_date_chip_specs(date(2026, 4, 1), None, None)
    assert specs == [("batch_date", "Batch date", date(2026, 4, 1))]


def test_batch_actual_start_on_different_day() -> None:
    specs = production_batch_date_chip_specs(
        date(2026, 4, 1),
        datetime(2026, 4, 2, 9, 0),
        datetime(2026, 4, 5, 14, 30),
    )
    assert len(specs) == 2
    assert specs[1] == ("actual_start", "Actual start", date(2026, 4, 5))


def test_batch_link_contains_batch_id() -> None:
    assert build_production_batch_calendar_link(99) == "/production?batchId=99"
