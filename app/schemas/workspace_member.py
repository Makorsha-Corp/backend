"""WorkspaceMember schemas"""
from pydantic import BaseModel, ConfigDict, field_validator
from datetime import datetime

VALID_MEMBER_ROLES = {'owner', 'manager', 'member', 'viewer', 'ground-team'}


class WorkspaceMemberBase(BaseModel):
    """Base workspace member schema"""
    workspace_id: int
    user_id: int
    role: str


class WorkspaceMemberCreate(WorkspaceMemberBase):
    """Workspace member creation schema"""
    position: str | None = None
    invited_by_user_id: int | None = None
    status: str = 'active'
    joined_at: datetime | None = None


class WorkspaceMemberUpdate(BaseModel):
    """Workspace member update schema"""
    role: str | None = None
    position: str | None = None
    status: str | None = None


class WorkspaceMemberResponse(WorkspaceMemberBase):
    """Workspace member response schema"""
    id: int
    invited_by_user_id: int | None
    invited_at: datetime
    joined_at: datetime | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkspaceMemberWithUser(WorkspaceMemberResponse):
    """Workspace member response with user details"""
    user_name: str | None = None
    user_email: str | None = None
    user_position: str | None = None


class RoleChangeRequest(BaseModel):
    """Request schema for changing user role and/or position"""
    new_role: str
    position: str | None = None

    @field_validator('new_role')
    @classmethod
    def validate_role(cls, v: str) -> str:
        allowed = VALID_MEMBER_ROLES - {'owner'}
        if v not in allowed:
            raise ValueError(f"Invalid role. Must be one of: {', '.join(sorted(allowed))}")
        return v
