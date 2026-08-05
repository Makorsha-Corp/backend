"""Platform waitlist admin access — email allowlist from env."""
from fastapi import Depends, HTTPException, status

from app.core.config import settings
from app.core.deps import get_current_active_user
from app.models.profile import Profile


def get_waitlist_admin(current_user: Profile = Depends(get_current_active_user)) -> Profile:
    allowlist = {
        email.strip().lower()
        for email in settings.WAITLIST_ADMIN_EMAILS
        if email.strip()
    }
    if not allowlist:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Waitlist admin access is not configured",
        )

    user_email = (current_user.email or "").strip().lower()
    if user_email not in allowlist:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view waitlist signups",
        )

    return current_user
