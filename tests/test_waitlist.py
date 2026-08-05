"""Waitlist signup service and route tests."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.main import app
from app.schemas.waitlist import WaitlistSignupRequest
from app.services.waitlist_service import (
    SUCCESS_MESSAGE,
    normalize_waitlist_email,
    waitlist_service,
)

WAITLIST_PATH = "/api/v1/waitlist"


def test_waitlist_routes_registered() -> None:
    paths = app.openapi()["paths"]
    assert WAITLIST_PATH in paths
    assert "post" in paths[WAITLIST_PATH]
    assert "get" in paths[WAITLIST_PATH]


def test_normalize_waitlist_email() -> None:
    assert normalize_waitlist_email("  User@Example.COM ") == "user@example.com"


@pytest.mark.anyio
async def test_verify_turnstile_skips_in_dev_without_secret() -> None:
    with patch("app.services.waitlist_service.settings") as mock_settings:
        mock_settings.TURNSTILE_SECRET_KEY = ""
        mock_settings.ENVIRONMENT = "development"
        await waitlist_service.verify_turnstile("token", "127.0.0.1")


@pytest.mark.anyio
async def test_verify_turnstile_rejects_invalid_token() -> None:
    with patch("app.services.waitlist_service.settings") as mock_settings:
        mock_settings.TURNSTILE_SECRET_KEY = "secret"
        mock_response = MagicMock()
        mock_response.json.return_value = {"success": False}
        mock_response.raise_for_status = MagicMock()
        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch("app.services.waitlist_service.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(HTTPException) as exc:
                await waitlist_service.verify_turnstile("bad-token", "127.0.0.1")
            assert exc.value.status_code == 400


def test_submit_signup_honeypot_returns_success_without_db_write() -> None:
    db = MagicMock()
    payload = WaitlistSignupRequest(
        email="user@example.com",
        turnstile_token="token",
        website="bot-filled-this",
    )
    result = waitlist_service.submit_signup(db, payload=payload, remote_ip="1.2.3.4")
    assert result.ok is True
    assert result.message == SUCCESS_MESSAGE
    db.add.assert_not_called()


def test_submit_signup_duplicate_returns_silent_success() -> None:
    db = MagicMock()
    existing = MagicMock()
    payload = WaitlistSignupRequest(
        email="user@example.com",
        turnstile_token="token",
    )

    with patch("app.services.waitlist_service.waitlist_dao") as mock_dao:
        mock_dao.get_by_email.return_value = existing
        result = waitlist_service.submit_signup(db, payload=payload, remote_ip="1.2.3.4")

    assert result.ok is True
    mock_dao.create_signup.assert_not_called()
