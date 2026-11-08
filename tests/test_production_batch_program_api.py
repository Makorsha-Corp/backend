"""HTTP contract for production batch program routes."""
from datetime import date, datetime
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.core.deps import get_current_active_user, get_current_workspace, get_db
from app.core.exceptions import BusinessRuleError
from app.main import app
from app.models.production_batch_program import ProductionBatchProgram
from app.models.profile import Profile
from app.models.workspace import Workspace
from app.services.production_batch_service import ProductionBatchService


def _program(**overrides) -> ProductionBatchProgram:
    program = ProductionBatchProgram(
        id=4,
        workspace_id=10,
        factory_id=3,
        formula_id=8,
        first_start_at=datetime(2026, 10, 5, 6, 0),
        cadence="weekly",
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


def test_create_program_returns_201_and_batch_count():
    program = _program()
    client = _client()
    try:
        with (
            patch(
                "app.api.v1.endpoints.production_batch_programs.production_batch_service.create_program",
                return_value=program,
            ) as create_program,
            patch(
                "app.api.v1.endpoints.production_batch_programs.production_batch_service.program_batch_counts",
                return_value={4: 3},
            ),
            patch(
                "app.api.v1.endpoints.production_batch_programs.production_batch_service.program_batches",
                return_value=[],
            ),
        ):
            response = client.post(
                "/api/v1/production-batch-programs/",
                json={
                    "factory_id": 3,
                    "formula_id": 8,
                    "first_start_at": "2026-10-05T06:00:00",
                    "cadence": "weekly",
                    "end_date": "2026-10-19",
                },
            )
        assert response.status_code == 201
        body = response.json()
        assert body["id"] == 4
        assert body["factory_id"] == 3
        assert body["batch_count"] == 3
        assert create_program.call_args.kwargs["workspace_id"] == 10
        assert create_program.call_args.kwargs["user_id"] == 5
        assert create_program.call_args.kwargs["cadence"] == "weekly"
    finally:
        app.dependency_overrides.clear()


def test_stop_program_returns_program():
    program = _program(status="stopped")
    client = _client()
    try:
        with (
            patch(
                "app.api.v1.endpoints.production_batch_programs.production_batch_service.stop_program",
                return_value=program,
            ) as stop_program,
            patch(
                "app.api.v1.endpoints.production_batch_programs.production_batch_service.program_batch_counts",
                return_value={4: 3},
            ),
            patch(
                "app.api.v1.endpoints.production_batch_programs.production_batch_service.program_batches",
                return_value=[],
            ),
        ):
            response = client.post("/api/v1/production-batch-programs/4/stop/")
        assert response.status_code == 200
        assert response.json()["status"] == "stopped"
        assert response.json()["id"] == 4
        stop_program.assert_called_once()
        assert stop_program.call_args.args[1:] == (4, 10, 5)
    finally:
        app.dependency_overrides.clear()


def test_list_programs_filters_factory_in_workspace():
    program = _program()
    client = _client()
    try:
        with (
            patch(
                "app.api.v1.endpoints.production_batch_programs.production_batch_service.get_programs",
                return_value=[program],
            ) as get_programs,
            patch(
                "app.api.v1.endpoints.production_batch_programs.production_batch_service.program_batch_counts",
                return_value={4: 3},
            ) as counts,
            patch(
                "app.api.v1.endpoints.production_batch_programs.production_batch_service.program_batches",
                return_value=[],
            ),
        ):
            response = client.get("/api/v1/production-batch-programs/?factory_id=3")
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["factory_id"] == 3
        assert body[0]["batch_count"] == 3
        assert body[0]["occurrences"] == []
        assert get_programs.call_args.kwargs == {"workspace_id": 10, "factory_id": 3}
        assert counts.call_args.kwargs["workspace_id"] == 10
        assert counts.call_args.kwargs["program_ids"] == [4]
    finally:
        app.dependency_overrides.clear()


def test_create_program_business_rule_error_is_not_rewrapped():
    client = _client()
    try:
        with patch(
            "app.api.v1.endpoints.production_batch_programs.production_batch_service.create_program",
            side_effect=BusinessRuleError("Recipe has no steps"),
        ):
            response = client.post(
                "/api/v1/production-batch-programs/",
                json={
                    "factory_id": 3,
                    "formula_id": 8,
                    "first_start_at": "2026-10-05T06:00:00",
                    "cadence": "weekly",
                    "end_date": "2026-10-19",
                },
            )
        assert response.status_code == 422
        assert response.json()["detail"] == "Recipe has no steps"
    finally:
        app.dependency_overrides.clear()


def test_service_get_programs_is_workspace_and_factory_scoped():
    service = ProductionBatchService()
    db = MagicMock()
    service.batch_manager = MagicMock()
    service.batch_manager.get_programs.return_value = []

    result = service.get_programs(db, workspace_id=1, factory_id=3)

    assert result == []
    service.batch_manager.get_programs.assert_called_once_with(
        db, workspace_id=1, factory_id=3
    )
