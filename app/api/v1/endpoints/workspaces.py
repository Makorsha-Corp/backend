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
from fastapi import APIRouter, Depends, status, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

from app.core.deps import get_db, get_current_active_user, get_current_workspace
from app.models.profile import Profile
from app.models.workspace import Workspace
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
from app.managers.workspace_manager import workspace_manager
from app.dao.workspace import workspace_dao
from app.dao.workspace_member import workspace_member_dao
from app.dao.workspace_invitation import workspace_invitation_dao
from app.dao.profile import profile_dao


router = APIRouter()


# ============================================================================
# WORKSPACE OPERATIONS
# ============================================================================

@router.get(
    "",
    response_model=List[WorkspaceListItem],
    summary="List user's workspaces",
    description="Get all workspaces the current user is a member of"
)
def list_workspaces(
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    List all workspaces user is member of.

    Returns minimal workspace info for workspace switcher UI.
    """
    # Get user's memberships
    memberships = workspace_member_dao.get_by_user(db, user_id=current_user.id)
    active_memberships = [m for m in memberships if m.status == 'active']

    workspaces = []
    for membership in active_memberships:
        workspace = workspace_dao.get(db, id=membership.workspace_id)
        if workspace:
            workspaces.append(WorkspaceListItem(
                id=workspace.id,
                name=workspace.name,
                slug=workspace.slug,
                subscription_status=workspace.subscription_status,
                role=membership.role,
                is_owner=(workspace.owner_user_id == current_user.id)
            ))

    return workspaces


@router.post(
    "",
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
    """
    Create new workspace.

    User becomes owner of the new workspace.

    Raises:
        - 400 Bad Request: Validation errors
    """
    import traceback
    try:
        logger.info(f"[ENDPOINT] ===== CREATE WORKSPACE ENDPOINT HIT =====")
        logger.info(f"[ENDPOINT] Current user: {current_user.email} (ID: {current_user.id})")
        logger.info(f"[ENDPOINT] Workspace input data: {workspace_in.model_dump()}")
        logger.info(f"[ENDPOINT] About to call workspace_manager...")
        workspace = workspace_manager.create_workspace_with_owner(
            session=db,
            workspace_data=workspace_in,
            owner_user_id=current_user.id,
            subscription_plan_id=workspace_in.subscription_plan_id
        )

        # Commit transaction
        db.commit()
        db.refresh(workspace)

        return workspace

    except ValueError as e:
        logger.error(f"[ENDPOINT] ValueError during workspace creation: {e}")
        logger.error(f"[ENDPOINT] Traceback:", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"[ENDPOINT] ===== EXCEPTION CAUGHT =====")
        logger.error(f"[ENDPOINT] Exception type: {type(e).__name__}")
        logger.error(f"[ENDPOINT] Exception message: {str(e)}")
        logger.error(f"[ENDPOINT] Full traceback:")
        traceback.print_exc()
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Workspace creation failed: {str(e)}")


@router.get(
    "/{workspace_id}",
    response_model=WorkspaceWithPlan,
    summary="Get workspace details",
    description="Get detailed workspace information including subscription plan"
)
def get_workspace(
    workspace_id: int,
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get workspace details.

    Requires user to be member of workspace.

    Raises:
        - 403 Forbidden: User not member of workspace
        - 404 Not Found: Workspace not found
    """
    # Verify membership
    membership = workspace_member_dao.get_by_workspace_and_user(
        db, workspace_id=workspace_id, user_id=current_user.id
    )
    if not membership or membership.status != 'active':
        raise HTTPException(status_code=403, detail="You are not a member of this workspace")

    workspace = workspace_dao.get(db, id=workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    # Get plan details
    plan = workspace.subscription_plan if hasattr(workspace, 'subscription_plan') else None

    return WorkspaceWithPlan(
        **workspace.__dict__,
        plan_name=plan.name if plan else None,
        plan_display_name=plan.display_name if plan else None,
        max_members=plan.max_members if plan else None,
        max_storage_mb=plan.max_storage_mb if plan else None,
        max_orders_per_month=plan.max_orders_per_month if plan else None,
    )


@router.patch(
    "/{workspace_id}",
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
    """
    Update workspace details.

    Only workspace owner can update.

    Raises:
        - 403 Forbidden: User not owner
        - 404 Not Found: Workspace not found
    """
    workspace = workspace_dao.get(db, id=workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    # Verify ownership
    if workspace.owner_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only workspace owner can update workspace")

    # Update workspace
    updated_workspace = workspace_dao.update(db, db_obj=workspace, obj_in=workspace_update)
    db.commit()
    db.refresh(updated_workspace)

    return updated_workspace


# ============================================================================
# MEMBER MANAGEMENT
# ============================================================================

@router.get(
    "/{workspace_id}/members",
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
    """
    List workspace members.

    Requires user to be member of workspace.

    Raises:
        - 403 Forbidden: User not member of workspace
    """
    # Verify membership
    membership = workspace_member_dao.get_by_workspace_and_user(
        db, workspace_id=workspace_id, user_id=current_user.id
    )
    if not membership or membership.status != 'active':
        raise HTTPException(status_code=403, detail="You are not a member of this workspace")

    # Get all members
    members = workspace_member_dao.get_by_workspace(db, workspace_id=workspace_id)

    if not include_inactive:
        members = [m for m in members if m.status == 'active']

    # Enrich with user details
    members_with_users = []
    for member in members:
        user = profile_dao.get(db, id=member.user_id)
        members_with_users.append(WorkspaceMemberWithUser(
            **member.__dict__,
            user_name=user.name if user else None,
            user_email=user.email if user else None,
            user_position=user.position if user else None,
        ))

    return members_with_users


@router.patch(
    "/{workspace_id}/members/{user_id}/role",
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
    """
    Update member's role.

    Only workspace owner can change roles.

    Raises:
        - 403 Forbidden: User not owner or trying to change owner role
        - 404 Not Found: Member not found
    """
    workspace = workspace_dao.get(db, id=workspace_id)
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")

    # Verify ownership
    if workspace.owner_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only workspace owner can change member roles")

    # Get member
    member = workspace_member_dao.get_by_workspace_and_user(
        db, workspace_id=workspace_id, user_id=user_id
    )
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")

    # Cannot change owner's role
    if member.role == 'owner':
        raise HTTPException(status_code=403, detail="Cannot change workspace owner's role")

    # Update role
    member.role = role_change.new_role
    db.flush()
    db.commit()
    db.refresh(member)

    return member


@router.delete(
    "/{workspace_id}/members/{user_id}",
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
    """
    Remove member from workspace.

    Business rules:
    - Owner can remove anyone
    - Manager can only remove ground-team
    - Cannot remove owner

    Raises:
        - 403 Forbidden: Insufficient permissions
        - 404 Not Found: Member not found
    """
    # Get current user's membership
    current_membership = workspace_member_dao.get_by_workspace_and_user(
        db, workspace_id=workspace_id, user_id=current_user.id
    )
    if not current_membership or current_membership.status != 'active':
        raise HTTPException(status_code=403, detail="You are not a member of this workspace")

    try:
        workspace_manager.remove_member_from_workspace(
            session=db,
            workspace_id=workspace_id,
            user_id=user_id,
            remover_id=current_user.id,
            remover_role=current_membership.role
        )

        db.commit()

        return {"message": "Member removed successfully"}

    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to remove member: {str(e)}")


# ============================================================================
# INVITATION MANAGEMENT
# ============================================================================

@router.post(
    "/{workspace_id}/invitations",
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
    """
    Invite user to workspace.

    Only owner and managers can invite.

    Raises:
        - 403 Forbidden: Insufficient permissions
        - 400 Bad Request: Validation errors (email already member, etc.)
    """
    # Get current user's membership
    current_membership = workspace_member_dao.get_by_workspace_and_user(
        db, workspace_id=workspace_id, user_id=current_user.id
    )
    if not current_membership or current_membership.status != 'active':
        raise HTTPException(status_code=403, detail="You are not a member of this workspace")

    # Only owner and managers can invite
    if current_membership.role not in ['owner', 'ground-team-manager']:
        raise HTTPException(status_code=403, detail="Only owners and managers can send invitations")

    try:
        invitation = workspace_manager.create_invitation(
            session=db,
            workspace_id=workspace_id,
            email=invite_request.email,
            role=invite_request.role,
            inviter_id=current_user.id
        )

        db.commit()
        db.refresh(invitation)

        # TODO: Send invitation email
        # email_service.send_workspace_invitation(
        #     to=invite_request.email,
        #     workspace_name=workspace.name,
        #     inviter_name=current_user.name,
        #     invitation_token=invitation.invitation_token
        # )

        return invitation

    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to send invitation: {str(e)}")


@router.get(
    "/{workspace_id}/invitations",
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
    """
    List workspace invitations.

    Only owner and managers can view invitations.

    Raises:
        - 403 Forbidden: Insufficient permissions
    """
    # Get current user's membership
    current_membership = workspace_member_dao.get_by_workspace_and_user(
        db, workspace_id=workspace_id, user_id=current_user.id
    )
    if not current_membership or current_membership.status != 'active':
        raise HTTPException(status_code=403, detail="You are not a member of this workspace")

    # Only owner and managers can view invitations
    if current_membership.role not in ['owner', 'ground-team-manager']:
        raise HTTPException(status_code=403, detail="Only owners and managers can view invitations")

    # Get invitations
    if include_expired:
        from app.models.workspace_invitation import WorkspaceInvitation
        invitations = db.query(WorkspaceInvitation).filter(
            WorkspaceInvitation.workspace_id == workspace_id
        ).all()
    else:
        invitations = workspace_invitation_dao.get_pending_invitations(db, workspace_id=workspace_id)

    # Enrich with details
    workspace = workspace_dao.get(db, id=workspace_id)
    invitations_with_details = []
    for invitation in invitations:
        inviter = profile_dao.get(db, id=invitation.invited_by) if invitation.invited_by else None
        invitations_with_details.append(WorkspaceInvitationWithDetails(
            **invitation.__dict__,
            workspace_name=workspace.name if workspace else None,
            invited_by_name=inviter.name if inviter else None,
        ))

    return invitations_with_details


@router.post(
    "/{workspace_id}/invitations/accept",
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
    """
    Accept workspace invitation (existing users only).

    New users should register via /auth/register with invitation_token.

    Raises:
        - 400 Bad Request: Invalid invitation, email mismatch
    """
    try:
        # Validate invitation
        invitation = workspace_manager.validate_invitation_for_user(
            session=db,
            invitation_token=accept_request.token,
            user_email=current_user.email
        )

        # Accept invitation
        member = workspace_manager.accept_invitation(
            session=db,
            invitation_id=invitation.id,
            user_id=current_user.id
        )

        db.commit()
        db.refresh(member)

        return member

    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to accept invitation: {str(e)}")


@router.delete(
    "/{workspace_id}/invitations/{invitation_id}",
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
    """
    Cancel pending invitation.

    Owner/manager or original inviter can cancel.

    Raises:
        - 403 Forbidden: Insufficient permissions
        - 404 Not Found: Invitation not found
    """
    # Get current user's membership
    current_membership = workspace_member_dao.get_by_workspace_and_user(
        db, workspace_id=workspace_id, user_id=current_user.id
    )
    if not current_membership or current_membership.status != 'active':
        raise HTTPException(status_code=403, detail="You are not a member of this workspace")

    try:
        workspace_manager.cancel_invitation(
            session=db,
            invitation_id=invitation_id,
            canceller_id=current_user.id,
            canceller_role=current_membership.role,
            workspace_id=workspace_id
        )

        db.commit()

        return {"message": "Invitation cancelled successfully"}

    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to cancel invitation: {str(e)}")


# ============================================================================
# USER'S PENDING INVITATIONS
# ============================================================================

@router.get(
    "/me/invitations",
    response_model=List[WorkspaceInvitationWithDetails],
    summary="Get my pending invitations",
    description="Get all pending invitations for current user's email"
)
def get_my_invitations(
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get all pending invitations for current user.

    Returns invitations sent to user's email that are still pending.
    """
    invitations = workspace_invitation_dao.get_user_invitations(db, email=current_user.email)

    # Enrich with details
    invitations_with_details = []
    for invitation in invitations:
        workspace = workspace_dao.get(db, id=invitation.workspace_id)
        inviter = profile_dao.get(db, id=invitation.invited_by) if invitation.invited_by else None
        invitations_with_details.append(WorkspaceInvitationWithDetails(
            **invitation.__dict__,
            workspace_name=workspace.name if workspace else None,
            invited_by_name=inviter.name if inviter else None,
        ))

    return invitations_with_details
