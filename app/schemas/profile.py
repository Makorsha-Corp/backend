"""Profile schemas"""
from pydantic import BaseModel, EmailStr, ConfigDict, field_validator

from app.utils.timezone_validate import is_valid_iana_timezone


class ProfileBase(BaseModel):
    """Base profile schema"""
    name: str
    email: EmailStr


class ProfileCreate(ProfileBase):
    """Profile creation schema"""
    password: str


class ProfileUpdate(BaseModel):
    """Profile update schema"""
    name: str | None = None
    email: EmailStr | None = None
    password: str | None = None


class ProfileMeUpdate(BaseModel):
    """Self-service profile update (auth/me)."""
    name: str | None = None
    timezone: str | None = None

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        if not trimmed:
            return None
        if not is_valid_iana_timezone(trimmed):
            raise ValueError("Invalid IANA timezone identifier")
        return trimmed


class ProfileResponse(ProfileBase):
    """Profile response schema"""
    id: int
    user_id: str
    timezone: str | None = None

    model_config = ConfigDict(from_attributes=True)


class MeResponse(BaseModel):
    """GET /auth/me/ response."""
    user: ProfileResponse
    workspace: dict

