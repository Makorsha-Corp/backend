"""Template-anchored recurrence seeding was removed in favor of work order programs."""

from app.managers.work_order_template_manager import WorkOrderTemplateManager


def test_generate_drafts_for_anchored_range_is_no_op():
    manager = WorkOrderTemplateManager()
    assert manager.generate_drafts_for_anchored_range(
        session=None,  # type: ignore[arg-type]
        template=None,  # type: ignore[arg-type]
        machine_id=1,
        workspace_id=1,
        user_id=1,
    ) == []
