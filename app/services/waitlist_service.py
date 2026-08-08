"""Waitlist signup orchestration — Turnstile verify, storage, admin list."""
from __future__ import annotations

import hashlib
import httpx
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.dao.waitlist import waitlist_dao
from app.models.waitlist_signup import WaitlistSignup
from app.schemas.waitlist import (
    WaitlistSignupItem,
    WaitlistSignupListResponse,
    WaitlistSignupRequest,
    WaitlistSignupResponse,
)
from app.services.base_service import BaseService

TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
SUCCESS_MESSAGE = "You're on the list — we'll be in touch."


def normalize_waitlist_email(email: str) -> str:
    return email.strip().lower()


def hash_client_ip(ip: Optional[str]) -> Optional[str]:
    if not ip:
        return None
    salt = settings.WAITLIST_IP_HASH_SALT or settings.SECRET_KEY
    digest = hashlib.sha256(f"{salt}:{ip}".encode("utf-8")).hexdigest()
    return digest


class WaitlistService(BaseService):
    async def verify_turnstile(self, token: str, remote_ip: Optional[str]) -> None:
        secret = settings.TURNSTILE_SECRET_KEY
        if not secret:
            if settings.ENVIRONMENT == "development":
                return
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Waitlist verification is not configured",
            )

        payload = {"secret": secret, "response": token}
        if remote_ip:
            payload["remoteip"] = remote_ip

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(TURNSTILE_VERIFY_URL, data=payload)
                response.raise_for_status()
                result = response.json()
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Could not verify submission",
            ) from exc

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Verification failed — please try again",
            )

    def submit_signup(
        self,
        db: Session,
        *,
        payload: WaitlistSignupRequest,
        remote_ip: Optional[str],
        skip_turnstile: bool = False,
    ) -> WaitlistSignupResponse:
        if payload.website:
            return WaitlistSignupResponse(message=SUCCESS_MESSAGE)

        email = normalize_waitlist_email(str(payload.email))
        if waitlist_dao.get_by_email(db, email=email):
            return WaitlistSignupResponse(message=SUCCESS_MESSAGE)

        try:
            waitlist_dao.create_signup(
                db,
                email=email,
                first_name=payload.first_name.strip(),
                last_name=payload.last_name.strip(),
                company_name=(payload.company_name or "").strip() or None,
                wants_product_updates=payload.wants_product_updates,
                source=payload.source,
                ip_hash=hash_client_ip(remote_ip),
            )
            self._commit_transaction(db)
        except Exception:
            self._rollback_transaction(db)
            existing = waitlist_dao.get_by_email(db, email=email)
            if existing:
                return WaitlistSignupResponse(message=SUCCESS_MESSAGE)
            raise

        return WaitlistSignupResponse(message=SUCCESS_MESSAGE)

    def update_status(self, db: Session, *, signup_id: int, status_value: str) -> WaitlistSignupItem:
        signup: Optional[WaitlistSignup] = waitlist_dao.get(db, signup_id)
        if not signup:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Waitlist signup not found",
            )
        waitlist_dao.update_status(db, signup=signup, status=status_value)
        self._commit_transaction(db)
        return WaitlistSignupItem.model_validate(signup)

    def list_signups(
        self,
        db: Session,
        *,
        skip: int,
        limit: int,
        search: Optional[str],
        wants_product_updates: Optional[bool],
        status_value: Optional[str] = None,
    ) -> WaitlistSignupListResponse:
        items, total = waitlist_dao.list_signups(
            db,
            skip=skip,
            limit=limit,
            search=search,
            wants_product_updates=wants_product_updates,
            status=status_value,
        )
        return WaitlistSignupListResponse(
            items=items,
            total=total,
            skip=skip,
            limit=limit,
        )


waitlist_service = WaitlistService()
