"""Profile schemas"""
from pydantic import BaseModel, EmailStr, ConfigDict
from app.models.enums import RoleEnum


class ProfileBase(BaseModel):
    """Base profile schema"""
    name: str
    email: EmailStr
    permission: RoleEnum
    position: str


class ProfileCreate(ProfileBase):
    """Profile creation schema"""
    password: str


class ProfileUpdate(BaseModel):
    """Profile update schema"""
    name: str | None = None
    email: EmailStr | None = None
    permission: RoleEnum | None = None
    position: str | None = None
    password: str | None = None


class ProfileResponse(ProfileBase):
    """Profile response schema"""
    id: int
    user_id: str

    model_config = ConfigDict(from_attributes=True)
