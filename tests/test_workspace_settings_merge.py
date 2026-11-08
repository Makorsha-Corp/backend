"""Workspace settings shallow merge on PATCH."""
from unittest.mock import MagicMock

from app.schemas.workspace import WorkspaceUpdate
from app.services.workspace_service import WorkspaceService


def test_update_workspace_merges_settings():
    service = WorkspaceService()
    workspace = MagicMock()
    workspace.settings = {"timezone": "Asia/Dhaka", "production_machine_pick_policy": "soft"}
    workspace.owner_user_id = 1

    service.workspace_dao = MagicMock()
    service.workspace_dao.get.return_value = workspace
    service.workspace_dao.update.return_value = workspace

    db = MagicMock()
    service._commit_transaction = MagicMock()
    service._rollback_transaction = MagicMock()

    update = WorkspaceUpdate(settings={"production_machine_pick_policy": "block_unavailable"})
    service.update_workspace(db, workspace_id=1, current_user_id=1, workspace_update=update)

    passed = service.workspace_dao.update.call_args.kwargs["obj_in"]
    assert passed.settings == {
        "timezone": "Asia/Dhaka",
        "production_machine_pick_policy": "block_unavailable",
    }
