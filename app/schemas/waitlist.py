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


class WaitlistSignupRequest(BaseModel):
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
    email: str
    wants_product_updates: bool
    source: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class WaitlistSignupListResponse(BaseModel):
    items: list[WaitlistSignupItem]
    total: int
    skip: int
    limit: int
