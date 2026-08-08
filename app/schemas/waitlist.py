"""Waitlist request/response schemas."""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, EmailStr, Field


WaitlistSource = Literal[
    "waitlist_section",
    "hero",
    "pricing",
    "nav",
    "unknown",
]

WaitlistStatus = Literal["PENDING", "CONTACTED", "ACCEPTED", "DECLINED"]


class WaitlistSignupRequest(BaseModel):
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    company_name: Optional[str] = Field(None, max_length=200)
    email: EmailStr
    wants_product_updates: bool = False
    turnstile_token: str = Field(..., min_length=1)
    source: Optional[WaitlistSource] = "waitlist_section"
    website: Optional[str] = Field(None, description="Honeypot field — must be empty")


class WaitlistSignupResponse(BaseModel):
    ok: bool = True
    message: str = "You're on the list — we'll be in touch."


class WaitlistSignupItem(BaseModel):
    id: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company_name: Optional[str] = None
    email: str
    wants_product_updates: bool
    source: Optional[str] = None
    status: WaitlistStatus
    created_at: datetime

    model_config = {"from_attributes": True}


class WaitlistStatusUpdateRequest(BaseModel):
    status: WaitlistStatus


class WaitlistSignupListResponse(BaseModel):
    items: list[WaitlistSignupItem]
    total: int
    skip: int
    limit: int
