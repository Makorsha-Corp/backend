"""Schemas module"""

# Workspace schemas
from app.schemas.subscription_plan import (
    SubscriptionPlanBase,
    SubscriptionPlanCreate,
    SubscriptionPlanResponse,
    SubscriptionPlanUpdate,
)
from app.schemas.workspace import (
    WorkspaceBase,
    WorkspaceCreate,
    WorkspaceListItem,
    WorkspaceResponse,
    WorkspaceUpdate,
    WorkspaceWithPlan,
)
from app.schemas.workspace_audit_log import (
    WorkspaceAuditLogBase,
    WorkspaceAuditLogCreate,
    WorkspaceAuditLogResponse,
    WorkspaceAuditLogWithDetails,
)
from app.schemas.workspace_invitation import (
    AcceptInvitationRequest,
    InviteUserRequest,
    WorkspaceInvitationBase,
    WorkspaceInvitationCreate,
    WorkspaceInvitationResponse,
    WorkspaceInvitationWithDetails,
)
from app.schemas.workspace_member import (
    RoleChangeRequest,
    WorkspaceMemberBase,
    WorkspaceMemberCreate,
    WorkspaceMemberResponse,
    WorkspaceMemberUpdate,
    WorkspaceMemberWithUser,
)

__all__ = [
    # Subscription plan schemas
    "SubscriptionPlanBase",
    "SubscriptionPlanCreate",
    "SubscriptionPlanUpdate",
    "SubscriptionPlanResponse",
    # Workspace schemas
    "WorkspaceBase",
    "WorkspaceCreate",
    "WorkspaceUpdate",
    "WorkspaceResponse",
    "WorkspaceWithPlan",
    "WorkspaceListItem",
    # Workspace member schemas
    "WorkspaceMemberBase",
    "WorkspaceMemberCreate",
    "WorkspaceMemberUpdate",
    "WorkspaceMemberResponse",
    "WorkspaceMemberWithUser",
    "RoleChangeRequest",
    # Workspace invitation schemas
    "WorkspaceInvitationBase",
    "WorkspaceInvitationCreate",
    "WorkspaceInvitationResponse",
    "WorkspaceInvitationWithDetails",
    "InviteUserRequest",
    "AcceptInvitationRequest",
    # Workspace audit log schemas
    "WorkspaceAuditLogBase",
    "WorkspaceAuditLogCreate",
    "WorkspaceAuditLogResponse",
    "WorkspaceAuditLogWithDetails",
]
