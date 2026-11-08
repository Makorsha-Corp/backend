"""Route-first: recipes own route_id; routes do not store a formula pointer."""
from unittest.mock import MagicMock, patch

from app.managers.production_formula_manager import production_formula_manager
from app.managers.production_route_manager import production_route_manager
from app.schemas.production_route import ProductionRouteCreate


def test_create_route_ignores_formula_binding() -> None:
    session = MagicMock()
    data = ProductionRouteCreate(factory_id=1, name="Carding path")
    with patch.object(production_route_manager, "_require_factory"), patch(
        "app.managers.production_route_manager.production_route_dao.create",
        return_value=MagicMock(id=3),
    ) as created:
        production_route_manager.create_route(session, data, workspace_id=1, user_id=2)
    payload = created.call_args.kwargs["obj_in"]
    assert "formula_id" not in payload
    assert payload["name"] == "Carding path"


def test_replace_stages_from_route_links_by_route_step_id() -> None:
    session = MagicMock()
    formula = MagicMock(id=10, route_id=5)
    route = MagicMock(id=5)
    step = MagicMock(id=8, step_order=1, name="Card", production_line_id=4)
    with patch.object(production_formula_manager, "_require_route", return_value=route), patch.object(
        production_formula_manager.formula_stage_dao, "get_by_formula", return_value=[]
    ), patch(
        "app.managers.production_formula_manager.production_route_step_dao.get_by_route",
        return_value=[step],
    ), patch.object(production_formula_manager.formula_stage_dao, "create") as create_stage:
        production_formula_manager.replace_stages_from_route(session, formula, 1)
    body = create_stage.call_args.kwargs["obj_in"]
    assert body["route_step_id"] == 8
    assert body["is_used"] is True
    assert body["stage_order"] == 1
