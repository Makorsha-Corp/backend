"""
Workspace management endpoints

Provides workspace operations:
- List user's workspaces
- Create new workspace
- Get workspace details
- Update workspace
- Manage members (add, remove, update role)
- Send invitations
- Accept invitations (for existing users)
- List and cancel invitations
"""
from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.orm import Session
from typing import List

from app.core.deps import get_db, get_current_active_user
from app.models.profile import Profile
from app.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceUpdate,
    WorkspaceResponse,
    WorkspaceListItem,
    WorkspaceWithPlan,
)
from app.schemas.workspace_member import (
    WorkspaceMemberResponse,
    WorkspaceMemberWithUser,
    RoleChangeRequest,
)
from app.schemas.workspace_invitation import (
    WorkspaceInvitationResponse,
    WorkspaceInvitationWithDetails,
    InviteUserRequest,
    AcceptInvitationRequest,
)
from app.services.workspace_service import workspace_service


router = APIRouter()


# ============================================================================
# WORKSPACE OPERATIONS
# ============================================================================

@router.get(
    "/",
    response_model=List[WorkspaceListItem],
    summary="List user's workspaces",
    description="Get all workspaces the current user is a member of"
)
def list_workspaces(
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    pairs = workspace_service.list_user_workspaces(db, user_id=current_user.id)
    return [
        WorkspaceListItem(
            id=workspace.id,
            name=workspace.name,
            slug=workspace.slug,
            subscription_status=workspace.subscription_status,
            role=membership.role,
            is_owner=(workspace.owner_user_id == current_user.id),
        )
        for workspace, membership in pairs
    ]


@router.post(
    "/",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new workspace",
    description="""
    Create a new workspace with current user as owner.

    Automatically:
    - Adds user as workspace owner
    - Assigns default subscription plan (with 14-day trial)
    - Seeds default statuses, departments, and tags
    """
)
def create_workspace(
    workspace_in: WorkspaceCreate,
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return workspace_service.create_workspace(
        db, workspace_data=workspace_in, owner_user_id=current_user.id
    )


@router.get(
    "/{workspace_id}/",
    response_model=WorkspaceWithPlan,
    summary="Get workspace details",
    description="Get detailed workspace information including subscription plan"
)
def get_workspace(
    workspace_id: int,
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    workspace, plan = workspace_service.get_workspace_with_plan(
        db, workspace_id=workspace_id, requesting_user_id=current_user.id
    )
    return WorkspaceWithPlan(
        **workspace.__dict__,
        plan_name=plan.name if plan else None,
        plan_display_name=plan.display_name if plan else None,
        max_members=plan.max_members if plan else None,
        max_storage_mb=plan.max_storage_mb if plan else None,
        max_orders_per_month=plan.max_orders_per_month if plan else None,
    )


@router.patch(
    "/{workspace_id}/",
    response_model=WorkspaceResponse,
    summary="Update workspace",
    description="Update workspace details (owner only)"
)
def update_workspace(
    workspace_id: int,
    workspace_update: WorkspaceUpdate,
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return workspace_service.update_workspace(
        db,
        workspace_id=workspace_id,
        current_user_id=current_user.id,
        workspace_update=workspace_update,
    )


# ============================================================================
# MEMBER MANAGEMENT
# ============================================================================

@router.get(
    "/{workspace_id}/members/",
    response_model=List[WorkspaceMemberWithUser],
    summary="List workspace members",
    description="Get all members of a workspace with user details"
)
def list_members(
    workspace_id: int,
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    include_inactive: bool = Query(False, description="Include inactive members")
):
    pairs = workspace_service.list_members(
        db,
        workspace_id=workspace_id,
        requesting_user_id=current_user.id,
        include_inactive=include_inactive,
    )
    return [
        WorkspaceMemberWithUser(
            **member.__dict__,
            user_name=user.name if user else None,
            user_email=user.email if user else None,
            user_position=member.position,
        )
        for member, user in pairs
    ]


@router.patch(
    "/{workspace_id}/members/{user_id}/role/",
    response_model=WorkspaceMemberResponse,
    summary="Update member role",
    description="Update workspace member's role (owner only)"
)
def update_member_role(
    workspace_id: int,
    user_id: int,
    role_change: RoleChangeRequest,
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return workspace_service.update_member_role(
        db,
        workspace_id=workspace_id,
        owner_user_id=current_user.id,
        target_user_id=user_id,
        new_role=role_change.new_role,
        position=role_change.position,
    )


@router.delete(
    "/{workspace_id}/members/{user_id}/",
    status_code=status.HTTP_200_OK,
    summary="Remove member from workspace",
    description="Remove a member from workspace (owner or manager only)"
)
def remove_member(
    workspace_id: int,
    user_id: int,
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    workspace_service.remove_member(
        db,
        workspace_id=workspace_id,
        remover_user_id=current_user.id,
        target_user_id=user_id,
    )
    return {"message": "Member removed successfully"}


# ============================================================================
# INVITATION MANAGEMENT
# ============================================================================

@router.post(
    "/{workspace_id}/invitations/",
    response_model=WorkspaceInvitationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Invite user to workspace",
    description="""
    Send invitation to join workspace.

    Generates secure token and creates pending invitation.
    Email should be sent separately (not implemented yet).
    """
)
def send_invitation(
    workspace_id: int,
    invite_request: InviteUserRequest,
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    invitation = workspace_service.send_invitation(
        db,
        workspace_id=workspace_id,
        inviter_user_id=current_user.id,
        email=invite_request.email,
        role=invite_request.role,
        position=invite_request.position,
    )

    # TODO: Send invitation email
    # email_service.send_workspace_invitation(...)

    return invitation


@router.get(
    "/{workspace_id}/invitations/",
    response_model=List[WorkspaceInvitationWithDetails],
    summary="List workspace invitations",
    description="Get all pending invitations for workspace"
)
def list_invitations(
    workspace_id: int,
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    include_expired: bool = Query(False, description="Include expired invitations")
):
    triples = workspace_service.list_invitations(
        db,
        workspace_id=workspace_id,
        requesting_user_id=current_user.id,
        include_expired=include_expired,
    )
    return [
        WorkspaceInvitationWithDetails(
            **invitation.__dict__,
            workspace_name=workspace.name if workspace else None,
            invited_by_name=inviter.name if inviter else None,
        )
        for invitation, workspace, inviter in triples
    ]


@router.post(
    "/{workspace_id}/invitations/accept/",
    response_model=WorkspaceMemberResponse,
    summary="Accept invitation (for existing users)",
    description="""
    Accept workspace invitation for existing user.

    For new users, use /auth/register with invitation_token instead.
    """
)
def accept_invitation(
    workspace_id: int,
    accept_request: AcceptInvitationRequest,
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    return workspace_service.accept_invitation(
        db,
        workspace_id=workspace_id,
        token=accept_request.token,
        current_user_id=current_user.id,
        current_user_email=current_user.email,
        position=accept_request.position,
    )


@router.delete(
    "/{workspace_id}/invitations/{invitation_id}/",
    status_code=status.HTTP_200_OK,
    summary="Cancel invitation",
    description="Cancel pending workspace invitation"
)
def cancel_invitation(
    workspace_id: int,
    invitation_id: int,
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    workspace_service.cancel_invitation(
        db,
        workspace_id=workspace_id,
        invitation_id=invitation_id,
        canceller_user_id=current_user.id,
    )
    return {"message": "Invitation cancelled successfully"}


# ============================================================================
# USER'S PENDING INVITATIONS
# ============================================================================

@router.get(
    "/me/invitations/",
    response_model=List[WorkspaceInvitationWithDetails],
    summary="Get my pending invitations",
    description="Get all pending invitations for current user's email"
)
def get_my_invitations(
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    triples = workspace_service.get_my_invitations(db, user_email=current_user.email)
    return [
        WorkspaceInvitationWithDetails(
            **invitation.__dict__,
            workspace_name=workspace.name if workspace else None,
            invited_by_name=inviter.name if inviter else None,
        )
        for invitation, workspace, inviter in triples
    ]
