"""Production formula stage item API registration and expected-output sync."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from app.managers.production_formula_manager import production_formula_manager


def test_production_formula_stage_item_paths_exist() -> None:
    from app.main import app

    paths = app.openapi()["paths"]
    assert "/api/v1/production-formulas/{formula_id}/stage-items/" in paths
    assert "/api/v1/production-formulas/{formula_id}/stages/{stage_id}/items/" in paths
    assert "/api/v1/production-formulas/{formula_id}/stages/{stage_id}/ensure-input-handoff/" in paths
    assert "/api/v1/production-formulas/stage-items/{stage_item_id}/" in paths


def test_valid_item_roles_match_manager() -> None:
    assert production_formula_manager.VALID_ITEM_ROLES == {"input", "output", "waste", "byproduct"}


def test_pick_primary_output_stage_item_highest_qty_lowest_id_tie() -> None:
    rows = [
        SimpleNamespace(id=10, quantity=50, item_id=1),
        SimpleNamespace(id=5, quantity=100, item_id=2),
        SimpleNamespace(id=8, quantity=100, item_id=3),
    ]
    primary = production_formula_manager._pick_primary_output_stage_item(rows)
    assert primary is not None
    assert primary.id == 5
    assert primary.item_id == 2
    assert primary.quantity == 100


def test_pick_primary_output_stage_item_empty_returns_none() -> None:
    assert production_formula_manager._pick_primary_output_stage_item([]) is None


def test_sync_stage_expected_output_from_materials_sets_primary_and_clears() -> None:
    session = MagicMock()
    stage = SimpleNamespace(id=99)
    stage_obj_holder = {"stage": stage}

    def get_stage(*_args, **_kwargs):
        return stage_obj_holder["stage"]

    output_rows_holder: list = [
        SimpleNamespace(id=1, quantity=40, item_id=11),
        SimpleNamespace(id=2, quantity=90, item_id=22),
    ]

    def get_outputs(*_args, **_kwargs):
        return list(output_rows_holder)

    updates: list = []

    def update_stage(_session, *, db_obj, obj_in):
        updates.append(obj_in)
        return db_obj

    production_formula_manager.formula_stage_dao.get_by_id_and_workspace = MagicMock(
        side_effect=get_stage
    )
    production_formula_manager.formula_stage_item_dao.get_by_stage = MagicMock(
        side_effect=get_outputs
    )
    production_formula_manager.formula_stage_dao.update = MagicMock(side_effect=update_stage)

    production_formula_manager._sync_stage_expected_output_from_materials(
        session, formula_stage_id=7, workspace_id=1
    )
    assert updates[-1] == {"expected_output_quantity": 90, "expected_output_item_id": 22}

    output_rows_holder.clear()
    production_formula_manager._sync_stage_expected_output_from_materials(
        session, formula_stage_id=7, workspace_id=1
    )
    assert updates[-1] == {"expected_output_quantity": None, "expected_output_item_id": None}


def test_reconcile_handoff_adds_inputs_without_overwriting_qty() -> None:
    session = MagicMock()
    target_stage = SimpleNamespace(id=20)
    source_outputs = [
        SimpleNamespace(
            item_id=1,
            quantity=100,
            unit="kg",
            is_optional=False,
            tolerance_percentage=None,
        ),
        SimpleNamespace(
            item_id=2,
            quantity=50,
            unit=None,
            is_optional=False,
            tolerance_percentage=None,
        ),
    ]
    existing_input = SimpleNamespace(id=9, item_id=1, quantity=77)

    created: list = []
    removed: list = []

    def get_inputs(*_args, **_kwargs):
        return [existing_input]

    def create_row(_session, *, obj_in):
        created.append(obj_in)
        return SimpleNamespace(**obj_in)

    def remove_row(_session, *, id):
        removed.append(id)

    production_formula_manager.formula_stage_item_dao.get_by_stage = MagicMock(side_effect=get_inputs)
    production_formula_manager.formula_stage_item_dao.create = MagicMock(side_effect=create_row)
    production_formula_manager.formula_stage_item_dao.remove = MagicMock(side_effect=remove_row)

    production_formula_manager._reconcile_handoff_inputs_from_outputs(
        session,
        target_stage=target_stage,
        source_outputs=source_outputs,
        workspace_id=1,
    )

    assert len(created) == 1
    assert created[0]["item_id"] == 2
    assert created[0]["quantity"] == 50
    assert removed == []


def test_apply_output_handoff_clears_next_inputs_when_outputs_removed() -> None:
    session = MagicMock()
    stage_one = SimpleNamespace(id=1, formula_id=10, stage_order=1)
    stage_two = SimpleNamespace(id=2, formula_id=10, stage_order=2)
    orphan_input = SimpleNamespace(id=55, item_id=3)

    production_formula_manager.formula_stage_dao.get_by_id_and_workspace = MagicMock(
        return_value=stage_one
    )
    production_formula_manager.formula_stage_dao.get_by_formula = MagicMock(
        return_value=[stage_one, stage_two]
    )
    production_formula_manager.formula_stage_item_dao.get_by_stage = MagicMock(
        side_effect=lambda *_a, formula_stage_id, **_k: (
            [] if formula_stage_id == stage_one.id else [orphan_input]
        )
    )
    removed: list = []
    production_formula_manager.formula_stage_item_dao.remove = MagicMock(
        side_effect=lambda _s, *, id: removed.append(id)
    )
    production_formula_manager.formula_stage_item_dao.create = MagicMock()

    production_formula_manager._apply_output_handoff_to_next_stage(
        session, formula_stage_id=stage_one.id, workspace_id=1
    )

    assert removed == [55]
    production_formula_manager.formula_stage_item_dao.create.assert_not_called()
