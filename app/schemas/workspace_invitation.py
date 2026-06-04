"""WorkspaceInvitation schemas"""
from pydantic import BaseModel, ConfigDict, EmailStr
from datetime import datetime
from typing import Optional

VALID_INVITE_ROLES = {'manager', 'member', 'viewer', 'ground-team'}


class WorkspaceInvitationBase(BaseModel):
    """Base workspace invitation schema"""
    email: EmailStr
    role: str
    position: str | None = None


class WorkspaceInvitationCreate(WorkspaceInvitationBase):
    """Workspace invitation creation schema"""
    workspace_id: int
    token: str
    invited_by_user_id: Optional[int] = None
    expires_at: datetime
    status: str = 'pending'


class WorkspaceInvitationResponse(WorkspaceInvitationBase):
    """Workspace invitation response schema"""
    id: int
    workspace_id: int
    invited_by_user_id: int | None
    token: str
    status: str  # 'pending', 'accepted', 'expired', 'cancelled'
    invited_at: datetime
    expires_at: datetime
    accepted_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class WorkspaceInvitationWithDetails(WorkspaceInvitationResponse):
    """Workspace invitation response with workspace details"""
    workspace_name: str | None = None
    invited_by_name: str | None = None


class InviteUserRequest(BaseModel):
    """Request schema for inviting user to workspace"""
    email: EmailStr
    role: str
    position: str | None = None


class AcceptInvitationRequest(BaseModel):
    """Request schema for accepting invitation"""
    token: str
    position: str | None = None
