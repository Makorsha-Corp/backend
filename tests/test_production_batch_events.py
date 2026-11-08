"""Production batch activity events."""
from datetime import date
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.core.deps import get_current_active_user, get_current_workspace, get_db
from app.core.exceptions import NotFoundError
from app.main import app
from app.models.profile import Profile
from app.models.production_batch import ProductionBatch
from app.models.workspace import Workspace
from app.models.production_batch_item import ProductionBatchItem
from app.models.production_batch_stage_log import ProductionBatchStageLog
from app.utils.production_batch_event_logging import (
    log_batch_event,
    log_batch_item_quantity_events,
    log_batch_update_events,
    log_stage_log_update_events,
)


def test_log_batch_event_flushes_row() -> None:
    session = MagicMock()
    event = log_batch_event(
        session,
        workspace_id=1,
        batch_id=2,
        event_type="batch_created",
        description="Batch created",
        performed_by=5,
    )
    session.add.assert_called_once()
    session.flush.assert_called_once()
    assert event.workspace_id == 1
    assert event.batch_id == 2
    assert event.event_type == "batch_created"


def test_batch_events_route_registered() -> None:
    paths = app.openapi()["paths"]
    assert "/api/v1/production-batches/{batch_id}/events/" in paths


def test_log_batch_update_events_skips_unchanged_fields() -> None:
    session = MagicMock()
    batch = ProductionBatch(
        id=3,
        workspace_id=10,
        batch_number="B-1",
        production_line_id=1,
        status="draft",
        batch_date=date(2026, 10, 5),
        notes="same",
    )
    log_batch_update_events(
        session,
        batch=batch,
        update_dict={"notes": "same"},
        user_id=7,
    )
    session.add.assert_not_called()


def test_list_batch_events_endpoint_returns_rows() -> None:
    user = Profile(id=5, name="U", email="u@t.com", user_id="u5", hashed_password="x")
    workspace = Workspace(id=10, name="Acme", slug="acme")
    db = MagicMock()

    app.dependency_overrides[get_current_active_user] = lambda: user
    app.dependency_overrides[get_current_workspace] = lambda: workspace
    app.dependency_overrides[get_db] = lambda: db
    try:
        with patch(
            "app.api.v1.endpoints.production_batches.production_batch_service.list_batch_events",
            return_value=[
                {
                    "id": 1,
                    "workspace_id": 10,
                    "batch_id": 99,
                    "batch_stage_log_id": None,
                    "event_type": "batch_created",
                    "description": "Batch created",
                    "metadata": None,
                    "performed_by": 5,
                    "user_name": "U",
                    "created_at": "2026-10-05T12:00:00+00:00",
                }
            ],
        ):
            client = TestClient(app)
            response = client.get(
                "/api/v1/production-batches/99/events/",
                headers={"X-Workspace-ID": "10"},
            )
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["event_type"] == "batch_created"
    finally:
        app.dependency_overrides.clear()


def test_list_batch_events_endpoint_404_when_batch_missing() -> None:
    user = Profile(id=5, name="U", email="u@t.com", user_id="u5", hashed_password="x")
    workspace = Workspace(id=10, name="Acme", slug="acme")
    db = MagicMock()

    app.dependency_overrides[get_current_active_user] = lambda: user
    app.dependency_overrides[get_current_workspace] = lambda: workspace
    app.dependency_overrides[get_db] = lambda: db
    try:
        with patch(
            "app.api.v1.endpoints.production_batches.production_batch_service.list_batch_events",
            side_effect=NotFoundError("Production batch 99 not found"),
        ):
            client = TestClient(app)
            response = client.get(
                "/api/v1/production-batches/99/events/",
                headers={"X-Workspace-ID": "10"},
            )
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


@patch("app.managers.production_batch_manager.log_batch_event")
def test_start_stage_log_writes_step_started(mock_log: MagicMock) -> None:
    from app.managers.production_batch_manager import ProductionBatchManager

    manager = ProductionBatchManager()
    session = MagicMock()
    log = MagicMock()
    log.id = 11
    log.batch_id = 22
    log.workspace_id = 10
    log.stage_name = "Spinning"
    log.status = "pending"
    log.formula_stage_id = None
    log.machine_id = None
    log.production_line_id = 3
    log.started_at = None

    updated = MagicMock()
    updated.id = 11
    updated.machine_id = 4

    with (
        patch.object(manager, "_require_stage_log", return_value=log),
        patch.object(manager, "_ensure_batch_running_for_step"),
        patch.object(manager, "_require_batch_in_progress"),
        patch.object(manager, "stage_log_dao") as mock_dao,
        patch.object(manager, "_flip_machine_for_live_step"),
        patch("app.managers.production_batch_manager.attach_stage_metrics", side_effect=lambda x: x),
        patch("app.managers.production_batch_manager.production_line_machine_dao") as mock_plm,
    ):
        mock_plm.get_machine_ids_for_line.return_value = [4]
        mock_dao.update.return_value = updated
        manager.start_stage_log(session, log_id=11, workspace_id=10, user_id=5)

    mock_log.assert_called_once()
    assert mock_log.call_args.kwargs["event_type"] == "step_started"
    assert "Spinning" in mock_log.call_args.kwargs["description"]


@patch("app.managers.production_batch_manager.log_batch_event")
def test_start_stage_log_flips_floor_when_started_earlier(mock_log: MagicMock) -> None:
    from datetime import datetime

    from app.managers.production_batch_manager import ProductionBatchManager

    manager = ProductionBatchManager()
    session = MagicMock()
    log = MagicMock()
    log.id = 11
    log.batch_id = 22
    log.workspace_id = 10
    log.stage_name = "Spinning"
    log.status = "pending"
    log.formula_stage_id = None
    log.machine_id = None
    log.production_line_id = 3
    log.started_at = None

    updated = MagicMock()
    updated.id = 11
    updated.machine_id = 4

    earlier = datetime(2020, 1, 1, 8, 0)
    with (
        patch.object(manager, "_require_stage_log", return_value=log),
        patch.object(manager, "_ensure_batch_running_for_step"),
        patch.object(manager, "_require_earlier_steps_closed"),
        patch.object(manager, "_enforce_machine_pick_policy"),
        patch.object(manager, "_validate_and_deduct_step_inputs"),
        patch.object(manager, "stage_log_dao") as mock_dao,
        patch.object(manager, "batch_dao") as mock_batch_dao,
        patch.object(manager, "_flip_machine_for_live_step") as flip,
        patch("app.managers.production_batch_manager.attach_stage_metrics", side_effect=lambda x: x),
        patch("app.managers.production_batch_manager.production_line_machine_dao") as mock_plm,
    ):
        mock_plm.get_machine_ids_for_line.return_value = [4]
        mock_dao.update.return_value = updated
        mock_batch_dao.get_by_id_and_workspace.return_value = MagicMock(id=22)
        manager.start_stage_log(
            session, log_id=11, workspace_id=10, user_id=5, started_at=earlier
        )

    flip.assert_called_once_with(session, updated, 10, 5, running=True)
    assert mock_log.call_args.kwargs["metadata"]["started_earlier"] is True


def test_flip_stays_running_when_another_step_is_live() -> None:
    from app.managers.production_batch_manager import production_batch_manager

    session = MagicMock()
    log = MagicMock(id=10, machine_id=5, batch_id=1, stage_name="Card")
    with (
        patch(
            "app.managers.machine_activity_manager.machine_activity_manager.get_latest_status",
            return_value=object(),
        ),
        patch(
            "app.managers.machine_activity_manager.machine_activity_manager.status_from_activity",
            return_value="RUNNING",
        ),
        patch(
            "app.managers.production_batch_manager.machine_has_other_in_progress_step",
            return_value=True,
        ) as live,
        patch("app.managers.machine_manager.machine_manager.create_machine_event") as create,
    ):
        production_batch_manager._flip_machine_for_live_step(
            session, log, 1, 2, running=False
        )
    live.assert_called_once_with(
        session, workspace_id=1, machine_id=5, exclude_stage_log_id=10
    )
    create.assert_not_called()


def test_log_batch_item_quantity_events_includes_step() -> None:
    session = MagicMock()
    batch_item = ProductionBatchItem(
        id=1,
        workspace_id=10,
        batch_id=99,
        item_id=5,
        item_role="input",
        expected_quantity=10,
        actual_quantity=None,
    )
    log_batch_item_quantity_events(
        session,
        batch_item=batch_item,
        update_dict={"actual_quantity": 5},
        user_id=7,
        batch_stage_log_id=12,
        stage_name="Carding",
    )
    session.add.assert_called_once()
    event = session.add.call_args[0][0]
    assert event.batch_stage_log_id == 12
    assert event.metadata_json["stage_name"] == "Carding"
    assert event.metadata_json["before"] is None
    assert event.metadata_json["after"] == 5


def test_log_stage_log_update_events_output_quantity() -> None:
    session = MagicMock()
    log = ProductionBatchStageLog(
        id=12,
        workspace_id=10,
        batch_id=99,
        stage_name="Carding",
        stage_order=1,
        status="completed",
        output_quantity=100,
    )
    log_stage_log_update_events(
        session,
        log=log,
        update_dict={"output_quantity": 120},
        user_id=7,
        old_status="completed",
    )
    session.add.assert_called_once()
    event = session.add.call_args[0][0]
    assert event.event_type == "step_output_changed"
    assert event.metadata_json["before"] == 100
    assert event.metadata_json["after"] == 120
