"""Waitlist admin dependency tests."""
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.core.waitlist_admin import get_waitlist_admin
from app.models.profile import Profile


def _profile(*, email: str = "staff@makorsha.com", is_platform_admin: bool = False) -> Profile:
    user = Profile(
        id=1,
        name="Staff",
        email=email,
        user_id="u1",
        hashed_password="x",
    )
    user.is_platform_admin = is_platform_admin
    return user


def test_platform_admin_bypasses_email_allowlist() -> None:
    user = _profile(is_platform_admin=True)
    result = get_waitlist_admin(current_user=user)
    assert result is user


@patch("app.core.waitlist_admin.settings")
def test_email_allowlist_when_not_platform_admin(mock_settings: MagicMock) -> None:
    mock_settings.WAITLIST_ADMIN_EMAILS = ["allowed@example.com"]
    user = _profile(email="allowed@example.com", is_platform_admin=False)
    result = get_waitlist_admin(current_user=user)
    assert result is user


@patch("app.core.waitlist_admin.settings")
def test_rejects_email_not_on_allowlist(mock_settings: MagicMock) -> None:
    mock_settings.WAITLIST_ADMIN_EMAILS = ["allowed@example.com"]
    user = _profile(email="other@example.com", is_platform_admin=False)
    with pytest.raises(HTTPException) as exc:
        get_waitlist_admin(current_user=user)
    assert exc.value.status_code == 403


@patch("app.core.waitlist_admin.settings")
def test_rejects_when_no_allowlist_and_not_platform_admin(mock_settings: MagicMock) -> None:
    mock_settings.WAITLIST_ADMIN_EMAILS = []
    user = _profile(is_platform_admin=False)
    with pytest.raises(HTTPException) as exc:
        get_waitlist_admin(current_user=user)
    assert exc.value.status_code == 403
