"""HTTP contract for work order program routes."""
from datetime import date, datetime
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.core.deps import get_current_active_user, get_current_workspace, get_db
from app.main import app
from app.models.profile import Profile
from app.models.work_order_program import WorkOrderProgram
from app.models.workspace import Workspace


def _program(**overrides) -> WorkOrderProgram:
    program = WorkOrderProgram(
        id=7,
        workspace_id=10,
        factory_id=3,
        machine_id=5,
        work_order_type_id=2,
        title="Oil change — Loom 1",
        work_order_template_id=None,
        cadence="weekly",
        start_date=date(2026, 10, 5),
        end_date=date(2026, 10, 19),
        status="active",
        created_by=5,
        created_at=datetime(2026, 10, 5, 5, 0),
    )
    for key, value in overrides.items():
        setattr(program, key, value)
    return program


def _client():
    user = Profile(
        id=5,
        name="Workspace User",
        email="m@t.com",
        user_id="u5",
        hashed_password="x",
    )
    workspace = Workspace(id=10, name="Acme", slug="acme")
    app.dependency_overrides[get_current_active_user] = lambda: user
    app.dependency_overrides[get_current_workspace] = lambda: workspace
    app.dependency_overrides[get_db] = lambda: MagicMock()
    return TestClient(app)


def test_list_programs_returns_occurrences():
    program = _program()
    client = _client()
    try:
        with (
            patch(
                "app.api.v1.endpoints.work_order_programs.work_order_service.get_work_order_programs",
                return_value=[program],
            ),
            patch(
                "app.api.v1.endpoints.work_order_programs.work_order_service.program_work_order_counts",
                return_value={7: 2},
            ),
            patch(
                "app.api.v1.endpoints.work_order_programs.work_order_service.program_work_orders",
                return_value=[],
            ),
        ):
            response = client.get("/api/v1/work-order-programs/?factory_id=3")
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["work_order_count"] == 2
        assert body[0]["occurrences"] == []
    finally:
        app.dependency_overrides.clear()


def test_stop_program_returns_stopped():
    program = _program(status="stopped")
    client = _client()
    try:
        with (
            patch(
                "app.api.v1.endpoints.work_order_programs.work_order_service.stop_work_order_program",
                return_value=program,
            ),
            patch(
                "app.api.v1.endpoints.work_order_programs.work_order_service.program_work_order_counts",
                return_value={7: 2},
            ),
            patch(
                "app.api.v1.endpoints.work_order_programs.work_order_service.program_work_orders",
                return_value=[],
            ),
        ):
            response = client.post("/api/v1/work-order-programs/7/stop/")
        assert response.status_code == 200
        assert response.json()["status"] == "stopped"
    finally:
        app.dependency_overrides.clear()
