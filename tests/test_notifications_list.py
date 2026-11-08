"""GET /me/notifications/ integration (real DB when available)."""
from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from app.core.deps import get_current_active_user, get_current_workspace, get_db
from app.dao.notification import notification_dao
from app.db.session import SessionLocal
from app.main import app
from app.models.notification import Notification


def test_list_notifications_real_db():
    db = SessionLocal()
    try:
        row = db.query(Notification).first()
        if row is None:
            return
        workspace = SimpleNamespace(id=row.workspace_id)
        user = SimpleNamespace(id=row.recipient_user_id)

        def _db():
            yield db

        app.dependency_overrides[get_db] = _db
        app.dependency_overrides[get_current_workspace] = lambda: workspace
        app.dependency_overrides[get_current_active_user] = lambda: user

        client = TestClient(app)
        response = client.get(
            "/api/v1/me/notifications/",
            params={"unread_only": False, "skip": 0, "limit": 50},
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert "items" in body
        assert "entity_label" in body["items"][0]
    finally:
        app.dependency_overrides.clear()
        db.close()
