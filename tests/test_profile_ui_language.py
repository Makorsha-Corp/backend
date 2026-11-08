"""Profile ui_language preference tests."""
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from app.models.profile import Profile
from app.schemas.profile import ProfileMeUpdate
from app.services.auth_service import AuthService
from app.utils.profile_auth import profile_to_auth_dict


def test_profile_me_update_accepts_en_bn() -> None:
    assert ProfileMeUpdate(ui_language="en").ui_language == "en"
    assert ProfileMeUpdate(ui_language="bn").ui_language == "bn"


def test_profile_me_update_rejects_invalid_ui_language() -> None:
    with pytest.raises(ValidationError, match="ui_language must be en or bn"):
        ProfileMeUpdate(ui_language="fr")


def test_profile_to_auth_dict_includes_ui_language_default() -> None:
    user = Profile(
        id=1,
        name="Jane",
        email="jane@example.com",
        user_id="jane@example.com",
        hashed_password="hashed",
    )
    assert profile_to_auth_dict(user)["ui_language"] == "en"


def test_profile_to_auth_dict_includes_ui_language_bn() -> None:
    user = Profile(
        id=1,
        name="Jane",
        email="jane@example.com",
        user_id="jane@example.com",
        hashed_password="hashed",
        ui_language="bn",
    )
    assert profile_to_auth_dict(user)["ui_language"] == "bn"


def test_auth_service_update_current_user_persists_ui_language() -> None:
    db = MagicMock()
    user = Profile(
        id=1,
        name="Jane",
        email="jane@example.com",
        user_id="jane@example.com",
        hashed_password="hashed",
        ui_language="en",
    )
    service = AuthService()
    updated = service.update_current_user(
        db,
        user=user,
        update=ProfileMeUpdate(ui_language="bn"),
    )
    assert updated.ui_language == "bn"
    db.add.assert_called_once()
