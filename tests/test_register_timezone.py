"""Register timezone onboarding tests (MAK-29)."""
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from app.dao.profile import profile_dao
from app.managers.workspace_manager import WorkspaceManager
from app.models.profile import Profile
from app.schemas.auth import RegisterRequest
from app.schemas.profile import ProfileCreate
from app.schemas.workspace import WorkspaceCreate
from app.utils.profile_auth import profile_to_auth_dict


def test_register_request_accepts_valid_timezone() -> None:
    req = RegisterRequest(
        name="Jane Doe",
        email="jane@example.com",
        password="password123",
        timezone="Asia/Dhaka",
    )
    assert req.timezone == "Asia/Dhaka"


def test_register_request_rejects_invalid_timezone() -> None:
    with pytest.raises(ValidationError, match="Invalid IANA timezone"):
        RegisterRequest(
            name="Jane Doe",
            email="jane@example.com",
            password="password123",
            timezone="Not/A_Real_Zone",
        )


def test_profile_create_stores_timezone() -> None:
    profile_in = ProfileCreate(
        name="Jane Doe",
        email="jane@example.com",
        password="password123",
        timezone="Asia/Dhaka",
    )
    assert profile_in.timezone == "Asia/Dhaka"


def test_profile_dao_create_persists_timezone() -> None:
    db = MagicMock()
    profile_in = ProfileCreate(
        name="Jane Doe",
        email="jane@example.com",
        password="password123",
        timezone="Asia/Dhaka",
    )

    user = profile_dao.create(db, obj_in=profile_in)

    assert user.timezone == "Asia/Dhaka"
    db.add.assert_called_once()
    db.flush.assert_called_once()


def test_profile_to_auth_dict_includes_timezone() -> None:
    user = Profile(
        id=1,
        name="Jane Doe",
        email="jane@example.com",
        user_id="jane@example.com",
        hashed_password="hashed",
        timezone="Asia/Dhaka",
    )
    auth_dict = profile_to_auth_dict(user)
    assert auth_dict["timezone"] == "Asia/Dhaka"


def test_create_workspace_with_owner_seeds_timezone_from_owner() -> None:
    session = MagicMock()
    manager = WorkspaceManager()

    owner = Profile(
        id=42,
        name="Owner",
        email="owner@example.com",
        user_id="owner@example.com",
        hashed_password="hashed",
        timezone="Asia/Dhaka",
    )
    plan = MagicMock()
    plan.id = 1
    plan.is_active = True

    workspace_data = WorkspaceCreate(
        name="Acme Mill",
        slug="acme-mill",
        billing_email="owner@example.com",
    )

    captured_workspace = {}

    def capture_add(obj):
        captured_workspace["obj"] = obj

    def assign_workspace_id():
        obj = captured_workspace.get("obj")
        if obj is not None:
            obj.id = 99

    session.add.side_effect = capture_add
    session.flush.side_effect = assign_workspace_id

    plan.name = "free"

    with patch.object(manager.subscription_dao, "get_default_plan", return_value=plan), patch.object(
        manager.workspace_dao, "get_by_slug", return_value=None
    ), patch("app.managers.workspace_manager.profile_dao") as mock_profile_dao, patch(
        "app.managers.workspace_manager.seed_default_statuses"
    ), patch(
        "app.managers.workspace_manager.seed_po_workflow"
    ), patch(
        "app.managers.workspace_manager.seed_default_departments"
    ), patch(
        "app.managers.workspace_manager.seed_default_tags"
    ), patch(
        "app.managers.workspace_manager.seed_default_account_tags"
    ), patch.object(
        manager.member_dao, "create"
    ), patch.object(
        manager.audit_dao, "log_action"
    ):
        mock_profile_dao.get.return_value = owner
        workspace = manager.create_workspace_with_owner(
            session=session,
            workspace_data=workspace_data,
            owner_user_id=owner.id,
        )

    assert workspace.settings == {"timezone": "Asia/Dhaka"}


def test_register_endpoint_rejects_invalid_timezone() -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    response = client.post(
        "/api/v1/auth/register",
        json={
            "name": "Jane Doe",
            "email": "jane@example.com",
            "password": "password123",
            "timezone": "Not/A_Real_Zone",
        },
    )
    assert response.status_code == 400
