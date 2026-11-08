"""Profile payload helpers for auth responses."""
from __future__ import annotations

from app.models.profile import Profile


def profile_to_auth_dict(user: Profile) -> dict:
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "timezone": user.timezone,
        "use_24_hour_time": bool(getattr(user, "use_24_hour_time", True)),
        "ui_language": getattr(user, "ui_language", None) or "en",
        "is_platform_admin": bool(getattr(user, "is_platform_admin", False)),
        "help_guides_seen": getattr(user, "help_guides_seen", None),
    }
