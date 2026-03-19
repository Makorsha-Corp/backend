"""WorkspaceMember schemas"""
from pydantic import BaseModel, ConfigDict
from datetime import datetime


class WorkspaceMemberBase(BaseModel):
    """Base workspace member schema"""
    workspace_id: int
    user_id: int
    role: str  # 'owner', 'finance', 'ground-team', 'ground-team-manager'


class WorkspaceMemberCreate(WorkspaceMemberBase):
    """Workspace member creation schema"""
    invited_by_user_id: int | None = None
    status: str = 'active'


class WorkspaceMemberUpdate(BaseModel):
    """Workspace member update schema"""
    role: str | None = None
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
    """Request schema for changing user role"""
    new_role: str
