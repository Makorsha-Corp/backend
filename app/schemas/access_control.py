"""Access control schemas"""
from pydantic import BaseModel, ConfigDict
from app.models.enums import AccessControlTypeEnum, RoleEnum


class AccessControlBase(BaseModel):
    """Base access control schema"""
    type: AccessControlTypeEnum
    target: str
    role: RoleEnum


class AccessControlCreate(AccessControlBase):
    """Access control creation schema"""
    pass


class AccessControlUpdate(BaseModel):
    """Access control update schema"""
    type: AccessControlTypeEnum | None = None
    target: str | None = None
    role: RoleEnum | None = None


class AccessControlResponse(AccessControlBase):
    """Access control response schema"""
    id: int

    model_config = ConfigDict(from_attributes=True)
