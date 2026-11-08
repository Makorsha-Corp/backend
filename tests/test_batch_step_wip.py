from decimal import Decimal

from app.utils.batch_step_wip import (
    compute_remaining_wip,
    compute_wip_available_by_item,
    group_step_start_storage_inputs,
    leftover_handoff_lines,
    leftover_intermediate_wip,
    storage_needed_after_wip,
)


class _Log:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class _Stage:
    def __init__(self, id: int, expected_output_item_id=None):
        self.id = id
        self.expected_output_item_id = expected_output_item_id


class _StageItem:
    def __init__(self, id, formula_stage_id, item_id, item_role, quantity):
        self.id = id
        self.formula_stage_id = formula_stage_id
        self.item_id = item_id
        self.item_role = item_role
        self.quantity = quantity


def test_wip_from_completed_prior_step():
    logs = [
        _Log(
            id=1,
            stage_order=0,
            formula_stage_id=10,
            status="completed",
            output_quantity=Decimal("50"),
        ),
        _Log(id=2, stage_order=1, formula_stage_id=11, status="pending"),
    ]
    current = logs[1]
    stages = {10: _Stage(10, expected_output_item_id=100)}
    stage_items = {
        10: [_StageItem(1, 10, 100, "output", Decimal("50"))],
        11: [_StageItem(2, 11, 100, "input", Decimal("50"))],
    }
    wip = compute_wip_available_by_item(
        logs,
        current,
        multiplier=Decimal("1"),
        stages_by_id=stages,
        stage_items_by_stage=stage_items,
        batch_items=[],
    )
    assert wip[100] == Decimal("50")


class _StepRow:
    def __init__(self, item_id, item_role, expected_quantity, actual_quantity=None):
        self.item_id = item_id
        self.item_role = item_role
        self.expected_quantity = expected_quantity
        self.actual_quantity = actual_quantity


def test_step_row_actual_reduces_consumption():
    logs = [
        _Log(
            id=1,
            stage_order=0,
            formula_stage_id=10,
            status="completed",
            output_quantity=Decimal("100"),
        ),
        _Log(id=2, stage_order=1, formula_stage_id=11, status="completed", output_quantity=Decimal("70")),
    ]
    stages = {
        10: _Stage(10, expected_output_item_id=100),
        11: _Stage(11, expected_output_item_id=200),
    }
    step_items = {
        2: [_StepRow(100, "input", Decimal("100"), Decimal("80"))],
    }
    remaining = compute_remaining_wip(
        logs,
        multiplier=Decimal("1"),
        stages_by_id=stages,
        stage_items_by_stage={},
        batch_items=[],
        step_items_by_log=step_items,
    )
    leftover = leftover_intermediate_wip(remaining, {200: Decimal("70")})
    assert leftover[100] == Decimal("20")
    assert 200 not in leftover


def test_storage_needed_after_wip():
    pool = {100: Decimal("30")}
    from_wip, storage = storage_needed_after_wip(100, Decimal("50"), pool)
    assert from_wip == Decimal("30")
    assert storage == Decimal("20")
    assert pool[100] == Decimal("0")


def test_leftover_handoff_names_maker_and_later_use():
    logs = [
        _Log(
            id=1,
            stage_order=0,
            stage_name="Cloth Cutting",
            formula_stage_id=10,
            status="completed",
            output_quantity=Decimal("10"),
        ),
        _Log(
            id=2,
            stage_order=1,
            stage_name="Embroidery",
            formula_stage_id=11,
            status="completed",
            output_quantity=Decimal("5"),
        ),
    ]
    stages = {
        10: _Stage(10, expected_output_item_id=100),
        11: _Stage(11, expected_output_item_id=200),
    }
    stage_items = {
        11: [_StageItem(2, 11, 100, "input", Decimal("5"))],
    }
    lines = leftover_handoff_lines(
        logs,
        {100: Decimal("5")},
        multiplier=Decimal("1"),
        stages_by_id=stages,
        stage_items_by_stage=stage_items,
        batch_items=[],
    )
    assert len(lines) == 1
    assert lines[0]["from_stage_name"] == "Cloth Cutting"
    assert lines[0]["made"] == Decimal("10")
    assert lines[0]["used"] == Decimal("5")
    assert lines[0]["qty"] == Decimal("5")
    assert lines[0]["used_by"] == [{"stage_name": "Embroidery", "qty": Decimal("5")}]


def test_group_step_start_storage_inputs_uses_log_name():
    rows = [
        ("SYSTEM - PRODUCTION STEP START | B-1 | Cutting | step_log=2", 7, Decimal("4")),
        ("SYSTEM - PRODUCTION STEP START | B-1 | Cutting | step_log=2", 7, Decimal("1")),
        ("SYSTEM - PRODUCTION STEP START | B-1 | Sewing | step_log=9", 7, Decimal("2")),
    ]
    lines = group_step_start_storage_inputs(
        rows,
        stage_name_by_log_id={2: "Cloth Cutting"},
        stage_order_by_log_id={2: (0, 2), 9: (1, 9)},
    )
    assert lines == [
        {"item_id": 7, "qty": Decimal("5"), "stage_name": "Cloth Cutting"},
        {"item_id": 7, "qty": Decimal("2"), "stage_name": "Sewing"},
    ]
