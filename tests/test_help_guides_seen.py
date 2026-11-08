"""Help guide seen-state helpers and auth endpoints."""
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.core.deps import get_current_active_user, get_current_workspace, get_db
from app.main import app
from app.models.profile import Profile
from app.models.workspace import Workspace
from app.utils.help_guides_seen import (
    append_seen_tour,
    has_seen_tour,
    normalize_help_guides_seen,
    remove_seen_tours,
    reset_seen_tours,
    validate_tour_id,
)


def test_validate_tour_id_accepts_kebab_case() -> None:
    assert validate_tour_id("purchase-order-list") == "purchase-order-list"


def test_validate_tour_id_rejects_empty() -> None:
    with pytest.raises(ValueError):
        validate_tour_id("   ")


def test_append_seen_idempotent() -> None:
    seen = append_seen_tour(None, workspace_id=10, tour_id="orders-overview")
    seen = append_seen_tour(seen, workspace_id=10, tour_id="orders-overview")
    assert seen["by_workspace"]["10"] == ["orders-overview"]


def test_workspace_isolation() -> None:
    seen = append_seen_tour(None, workspace_id=10, tour_id="a")
    seen = append_seen_tour(seen, workspace_id=42, tour_id="b")
    assert has_seen_tour(seen, workspace_id=10, tour_id="a")
    assert not has_seen_tour(seen, workspace_id=10, tour_id="b")
    assert has_seen_tour(seen, workspace_id=42, tour_id="b")


def test_reset_workspace_only() -> None:
    seen = append_seen_tour(None, workspace_id=10, tour_id="a")
    seen = append_seen_tour(seen, workspace_id=42, tour_id="b")
    reset = reset_seen_tours(seen, workspace_id=10, scope="workspace")
    assert normalize_help_guides_seen(reset)["by_workspace"] == {"42": ["b"]}


def test_remove_seen_tours_keeps_other_ids() -> None:
    seen = append_seen_tour(None, workspace_id=10, tour_id="a")
    seen = append_seen_tour(seen, workspace_id=10, tour_id="b")
    out = remove_seen_tours(seen, workspace_id=10, tour_ids=["a"])
    assert out["by_workspace"]["10"] == ["b"]


def test_reset_all() -> None:
    seen = append_seen_tour(None, workspace_id=10, tour_id="a")
    reset = reset_seen_tours(seen, workspace_id=10, scope="all")
    assert reset == {"by_workspace": {}}


def test_mark_seen_endpoint_via_service() -> None:
    user = Profile(
        id=1,
        name="U",
        email="u@t.com",
        user_id="u1",
        hashed_password="x",
        help_guides_seen=None,
        use_24_hour_time=True,
        is_platform_admin=False,
    )
    workspace = Workspace(id=10, name="Acme", slug="acme")
    db = MagicMock()
    db.refresh = MagicMock()

    app.dependency_overrides[get_current_active_user] = lambda: user
    app.dependency_overrides[get_current_workspace] = lambda: workspace
    app.dependency_overrides[get_db] = lambda: db
    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/auth/me/help-guides/mark-seen",
            json={"tour_id": "orders-overview"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["help_guides_seen"]["by_workspace"]["10"] == ["orders-overview"]
        assert user.help_guides_seen["by_workspace"]["10"] == ["orders-overview"]
        response2 = client.post(
            "/api/v1/auth/me/help-guides/mark-seen",
            json={"tour_id": "orders-overview"},
        )
        assert response2.status_code == 200
        assert response2.json()["help_guides_seen"]["by_workspace"]["10"] == ["orders-overview"]
    finally:
        app.dependency_overrides.clear()


def test_reset_endpoint_workspace_scope() -> None:
    user = Profile(
        id=1,
        name="U",
        email="u@t.com",
        user_id="u1",
        hashed_password="x",
        help_guides_seen={"by_workspace": {"10": ["a"], "42": ["b"]}},
        use_24_hour_time=True,
        is_platform_admin=False,
    )
    workspace = Workspace(id=10, name="Acme", slug="acme")
    db = MagicMock()
    db.refresh = MagicMock()

    app.dependency_overrides[get_current_active_user] = lambda: user
    app.dependency_overrides[get_current_workspace] = lambda: workspace
    app.dependency_overrides[get_db] = lambda: db
    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/auth/me/help-guides/reset",
            json={"scope": "workspace"},
        )
        assert response.status_code == 200
        assert response.json()["help_guides_seen"]["by_workspace"] == {"42": ["b"]}
    finally:
        app.dependency_overrides.clear()
