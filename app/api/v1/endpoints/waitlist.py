"""Public waitlist signup and platform-admin listing."""
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.core.limiter import limiter
from app.core.waitlist_admin import get_waitlist_admin
from app.models.profile import Profile
from app.schemas.waitlist import (
    WaitlistSignupItem,
    WaitlistSignupListResponse,
    WaitlistSignupRequest,
    WaitlistSignupResponse,
    WaitlistStatus,
    WaitlistStatusUpdateRequest,
)
from app.services.waitlist_service import waitlist_service

router = APIRouter()


@router.post(
    "",
    response_model=WaitlistSignupResponse,
    status_code=status.HTTP_200_OK,
    summary="Join the platform waitlist",
)
@limiter.limit("5/minute")
async def join_waitlist(
    request: Request,
    payload: WaitlistSignupRequest,
    db: Session = Depends(get_db),
) -> WaitlistSignupResponse:
    remote_ip = request.client.host if request.client else None
    await waitlist_service.verify_turnstile(payload.turnstile_token, remote_ip)
    return waitlist_service.submit_signup(db, payload=payload, remote_ip=remote_ip)


@router.get(
    "",
    response_model=WaitlistSignupListResponse,
    summary="List waitlist signups (platform admin allowlist)",
)
def list_waitlist_signups(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    search: Optional[str] = Query(None, max_length=320),
    wants_product_updates: Optional[bool] = Query(None),
    status: Optional[WaitlistStatus] = Query(None),
    db: Session = Depends(get_db),
    _: Profile = Depends(get_waitlist_admin),
) -> WaitlistSignupListResponse:
    return waitlist_service.list_signups(
        db,
        skip=skip,
        limit=limit,
        search=search,
        wants_product_updates=wants_product_updates,
        status_value=status,
    )


@router.patch(
    "/{signup_id}/status",
    response_model=WaitlistSignupItem,
    summary="Update waitlist signup status (platform admin allowlist)",
)
def update_waitlist_signup_status(
    signup_id: int,
    payload: WaitlistStatusUpdateRequest,
    db: Session = Depends(get_db),
    _: Profile = Depends(get_waitlist_admin),
) -> WaitlistSignupItem:
    return waitlist_service.update_status(db, signup_id=signup_id, status_value=payload.status)
