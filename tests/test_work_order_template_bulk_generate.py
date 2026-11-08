"""Recurring draft generation moved to work order programs."""

from datetime import date, time
from types import SimpleNamespace

from app.managers.work_order_template_manager import WorkOrderTemplateManager
from app.utils.work_order_window import resolve_work_order_window


class _Query:
    def __init__(self, rows):
        self._rows = rows

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return self._rows


class _Session:
    def __init__(self, rows):
        self._rows = rows

    def query(self, _model):
        return _Query(self._rows)


def test_generate_drafts_for_anchored_range_returns_empty():
    manager = WorkOrderTemplateManager()
    assert (
        manager.generate_drafts_for_anchored_range(
            session=None,  # type: ignore[arg-type]
            template=None,  # type: ignore[arg-type]
            machine_id=5,
            workspace_id=1,
            user_id=7,
        )
        == []
    )


def test_afternoon_template_does_not_overlap_morning_order(monkeypatch):
    start, end = resolve_work_order_window(
        planned_date=date(2026, 11, 2),
        planned_start_time=time(6, 0),
        expected_duration_minutes=120,
        tz_name="Asia/Dhaka",
    )
    order = SimpleNamespace(planned_start_at=start, planned_end_at=end, planned_date=date(2026, 11, 2))
    template = SimpleNamespace(
        shift_id=None,
        planned_start_time=time(14, 0),
        expected_duration_minutes=None,
        work_order_type_id=10,
    )
    monkeypatch.setattr(
        "app.managers.work_order_manager.work_order_manager._workspace_timezone_name",
        lambda *args, **kwargs: "Asia/Dhaka",
    )
    manager = WorkOrderTemplateManager()
    assert manager._template_window_overlaps_open_order(
        _Session([order]),
        template=template,
        workspace_id=1,
        machine_id=5,
        target_date=date(2026, 11, 2),
    ) is False


def test_overlapping_clock_skips_open_order(monkeypatch):
    start, end = resolve_work_order_window(
        planned_date=date(2026, 11, 2),
        planned_start_time=time(6, 0),
        expected_duration_minutes=240,
        tz_name="Asia/Dhaka",
    )
    order = SimpleNamespace(planned_start_at=start, planned_end_at=end, planned_date=date(2026, 11, 2))
    template = SimpleNamespace(
        shift_id=None,
        planned_start_time=time(8, 0),
        expected_duration_minutes=60,
        work_order_type_id=10,
    )
    monkeypatch.setattr(
        "app.managers.work_order_manager.work_order_manager._workspace_timezone_name",
        lambda *args, **kwargs: "Asia/Dhaka",
    )
    manager = WorkOrderTemplateManager()
    assert manager._template_window_overlaps_open_order(
        _Session([order]),
        template=template,
        workspace_id=1,
        machine_id=5,
        target_date=date(2026, 11, 2),
    ) is True
