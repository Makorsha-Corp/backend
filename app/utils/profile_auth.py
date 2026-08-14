"""Profile payload helpers for auth responses."""
from __future__ import annotations

from app.models.profile import Profile


def profile_to_auth_dict(user: Profile) -> dict:
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "timezone": user.timezone,
    }
