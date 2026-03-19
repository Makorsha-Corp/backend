"""WorkspaceInvitation schemas"""
from pydantic import BaseModel, ConfigDict, EmailStr
from datetime import datetime


class WorkspaceInvitationBase(BaseModel):
    """Base workspace invitation schema"""
    email: EmailStr
    role: str  # 'owner', 'finance', 'ground-team', 'ground-team-manager'


class WorkspaceInvitationCreate(WorkspaceInvitationBase):
    """Workspace invitation creation schema"""
    workspace_id: int


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


class AcceptInvitationRequest(BaseModel):
    """Request schema for accepting invitation"""
    token: str
