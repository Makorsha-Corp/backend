"""Workspace Manager for workspace and member management"""
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import secrets
import logging

logger = logging.getLogger(__name__)
from app.managers.base_manager import BaseManager
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember
from app.models.workspace_invitation import WorkspaceInvitation
from app.dao.workspace import workspace_dao
from app.dao.workspace_member import workspace_member_dao
from app.dao.workspace_invitation import workspace_invitation_dao
from app.dao.workspace_audit_log import workspace_audit_log_dao
from app.dao.subscription_plan import subscription_plan_dao
from app.schemas.workspace import WorkspaceCreate
from app.schemas.workspace_member import WorkspaceMemberCreate
from app.schemas.workspace_invitation import WorkspaceInvitationCreate
from app.db.seed_default_statuses import seed_default_statuses
from app.db.seed_default_departments import seed_default_departments
from app.db.seed_default_tags import seed_default_tags
from app.db.seed_default_account_tags import seed_default_account_tags


class WorkspaceManager(BaseManager[Workspace]):
    """
    AGGREGATE MANAGER: Manages Workspace aggregate root.

    Aggregate: Workspace + WorkspaceMembers + WorkspaceInvitations + AuditLogs

    Business rules:
    - Workspace must have owner
    - Owner cannot be removed
    - Check subscription limits before adding members
    - Validate invitation emails
    - Email matching required for invitation acceptance

    Does NOT commit transactions - that's the service layer's responsibility.
    """

    def __init__(self):
        super().__init__(Workspace)
        self.workspace_dao = workspace_dao
        self.member_dao = workspace_member_dao
        self.invitation_dao = workspace_invitation_dao
        self.audit_dao = workspace_audit_log_dao
        self.subscription_dao = subscription_plan_dao

    def create_workspace_with_owner(
        self,
        session: Session,
        workspace_data: WorkspaceCreate,
        owner_user_id: int,
        subscription_plan_id: Optional[int] = None
    ) -> Workspace:
        """
        Create workspace with owner as first member.

        Business logic:
        - Workspace must have owner
        - Assigns subscription plan (provided or default)
        - Creates workspace
        - Adds owner as member with role='owner'
        - Seeds default data (statuses, departments, tags)
        - Logs creation event

        Args:
            session: Database session
            workspace_data: Workspace creation data
            owner_user_id: User ID who will be owner
            subscription_plan_id: Optional subscription plan ID

        Returns:
            Created workspace (not yet committed)

        Raises:
            ValueError: If subscription plan invalid

        Note:
            This method does NOT commit. Service layer must commit.
        """
        # Get subscription plan
        if subscription_plan_id:
            plan = self.subscription_dao.get(session, id=subscription_plan_id)
            if not plan or not plan.is_active:
                raise ValueError("Invalid subscription plan")
        else:
            plan = self.subscription_dao.get_default_plan(session)
            if not plan:
                raise ValueError("No default subscription plan found")

        # Create workspace
        workspace_dict = workspace_data.model_dump()
        workspace_dict['subscription_plan_id'] = plan.id
        workspace_dict['owner_user_id'] = owner_user_id
        workspace_dict['created_by_user_id'] = owner_user_id

        # Create trial_ends_at datetime
        trial_ends = datetime.utcnow() + timedelta(days=14)  # 14-day trial
        logger.info(f"[WORKSPACE] Created trial_ends_at: type={type(trial_ends).__name__}, value={repr(trial_ends)}")
        workspace_dict['trial_ends_at'] = trial_ends

        logger.info(f"[WORKSPACE] workspace_dict keys: {workspace_dict.keys()}")
        logger.info(f"[WORKSPACE] Creating Workspace object...")

        workspace = Workspace(**workspace_dict)

        logger.info(f"[WORKSPACE] Workspace object created, adding to session...")
        session.add(workspace)

        logger.info(f"[WORKSPACE] Flushing to database...")
        session.flush()  # Get workspace.id
        logger.info(f"[WORKSPACE] Flush successful! workspace.id={workspace.id}")

        # Add owner as member
        joined_at = datetime.utcnow()
        logger.info(f"[WORKSPACE] Created joined_at: type={type(joined_at).__name__}, value={repr(joined_at)}")

        member_in = WorkspaceMemberCreate(
            workspace_id=workspace.id,
            user_id=owner_user_id,
            role='owner',
            status='active',
            joined_at=joined_at
        )
        logger.info(f"[WORKSPACE] Creating workspace member...")
        self.member_dao.create(session, obj_in=member_in)
        logger.info(f"[WORKSPACE] Member created successfully")

        # Seed default data for workspace
        seed_default_statuses(session, workspace_id=workspace.id)
        seed_default_departments(session, workspace_id=workspace.id)
        seed_default_tags(session, workspace_id=workspace.id, created_by_user_id=owner_user_id)
        seed_default_account_tags(session, workspace_id=workspace.id, created_by_user_id=owner_user_id)

        # Log workspace creation
        self.audit_dao.log_action(
            session,
            workspace_id=workspace.id,
            user_id=owner_user_id,
            action='workspace_created',
            metadata={'plan': plan.name}
        )

        return workspace

    def add_member_to_workspace(
        self,
        session: Session,
        workspace_id: int,
        user_id: int,
        role: str,
        inviter_id: int
    ) -> WorkspaceMember:
        """
        Add member to workspace with validation.

        Business rules:
        - Check subscription.max_members limit
        - Cannot add duplicate members
        - Validate role is valid

        Args:
            session: Database session
            workspace_id: Workspace ID
            user_id: User to add
            role: User's role (owner, finance, ground-team-manager, ground-team)
            inviter_id: User adding the member

        Returns:
            Created workspace member (not yet committed)

        Raises:
            ValueError: If business rules violated

        Note:
            This method does NOT commit. Service layer must commit.
        """
        # Validate role
        valid_roles = ['owner', 'finance', 'ground-team-manager', 'ground-team']
        if role not in valid_roles:
            raise ValueError(f"Invalid role. Must be one of: {', '.join(valid_roles)}")

        # Check if user already member
        existing = self.member_dao.get_by_workspace_and_user(
            session, workspace_id=workspace_id, user_id=user_id
        )
        if existing:
            raise ValueError("User is already a member of this workspace")

        # Check subscription limits
        workspace = self.workspace_dao.get(session, id=workspace_id)
        if not workspace:
            raise ValueError("Workspace not found")

        plan = self.subscription_dao.get(session, id=workspace.subscription_plan_id)
        if plan and plan.max_members:
            current_member_count = self.member_dao.count_active_members(
                session, workspace_id=workspace_id
            )
            if current_member_count >= plan.max_members:
                raise ValueError(
                    f"Workspace has reached maximum member limit ({plan.max_members}). "
                    f"Upgrade subscription to add more members."
                )

        # Create member
        member_in = WorkspaceMemberCreate(
            workspace_id=workspace_id,
            user_id=user_id,
            role=role,
            status='active',
            joined_at=datetime.utcnow()
        )
        member = self.member_dao.create(session, obj_in=member_in)

        # Log event
        self.audit_dao.log_action(
            session,
            workspace_id=workspace_id,
            user_id=inviter_id,
            action='member_added',
            metadata={'new_member_id': user_id, 'role': role}
        )

        return member

    def remove_member_from_workspace(
        self,
        session: Session,
        workspace_id: int,
        user_id: int,
        remover_id: int,
        remover_role: str
    ) -> None:
        """
        Remove member from workspace with validation.

        Business rules:
        - Cannot remove owner
        - Owner can remove anyone
        - Managers can remove ground-team only
        - Ground-team cannot remove anyone

        Args:
            session: Database session
            workspace_id: Workspace ID
            user_id: User to remove
            remover_id: User performing removal
            remover_role: Role of user performing removal

        Raises:
            ValueError: If business rules violated

        Note:
            This method does NOT commit. Service layer must commit.
        """
        # Get member to remove
        member = self.member_dao.get_by_workspace_and_user(
            session, workspace_id=workspace_id, user_id=user_id
        )
        if not member:
            raise ValueError("User is not a member of this workspace")

        # Business rule: Cannot remove owner
        if member.role == 'owner':
            raise ValueError("Cannot remove workspace owner. Transfer ownership first.")

        # Business rule: Check permissions
        if remover_role == 'ground-team':
            raise ValueError("You do not have permission to remove members")

        if remover_role == 'ground-team-manager' and member.role != 'ground-team':
            raise ValueError("Managers can only remove ground-team members")

        # Update member status to inactive
        member.status = 'inactive'
        member.left_at = datetime.utcnow()
        session.flush()

        # Log event
        self.audit_dao.log_action(
            session,
            workspace_id=workspace_id,
            user_id=remover_id,
            action='member_removed',
            metadata={'removed_member_id': user_id}
        )

    def create_invitation(
        self,
        session: Session,
        workspace_id: int,
        email: str,
        role: str,
        inviter_id: int
    ) -> WorkspaceInvitation:
        """
        Create workspace invitation with validation.

        Business rules:
        - Check subscription.max_members limit
        - Email not already a member
        - Email not already invited (pending)
        - Generate secure random token

        Args:
            session: Database session
            workspace_id: Workspace ID
            email: Email to invite
            role: Role to assign
            inviter_id: User sending invitation

        Returns:
            Created invitation (not yet committed)

        Raises:
            ValueError: If business rules violated

        Note:
            This method does NOT commit. Service layer must commit.
        """
        # Validate role
        valid_roles = ['finance', 'ground-team-manager', 'ground-team']
        if role not in valid_roles:
            raise ValueError(f"Invalid role. Must be one of: {', '.join(valid_roles)}")

        # Check if email already member
        from app.dao.profile import profile_dao
        user = profile_dao.get_by_email(session, email=email)
        if user:
            existing_member = self.member_dao.get_by_workspace_and_user(
                session, workspace_id=workspace_id, user_id=user.id
            )
            if existing_member and existing_member.status == 'active':
                raise ValueError("User with this email is already a member of this workspace")

        # Check if already invited (pending)
        existing_invitation = self.invitation_dao.get_by_workspace_and_email(
            session, workspace_id=workspace_id, email=email
        )
        if existing_invitation and existing_invitation.status == 'pending':
            if existing_invitation.expires_at > datetime.utcnow():
                raise ValueError("An invitation has already been sent to this email")

        # Check subscription limits
        workspace = self.workspace_dao.get(session, id=workspace_id)
        if not workspace:
            raise ValueError("Workspace not found")

        plan = self.subscription_dao.get(session, id=workspace.subscription_plan_id)
        if plan and plan.max_members:
            current_member_count = self.member_dao.count_active_members(
                session, workspace_id=workspace_id
            )
            # Count pending invitations as well
            pending_invitations = self.invitation_dao.count_pending_invitations(
                session, workspace_id=workspace_id
            )
            if (current_member_count + pending_invitations) >= plan.max_members:
                raise ValueError(
                    f"Workspace has reached maximum member limit ({plan.max_members}). "
                    f"Upgrade subscription to add more members."
                )

        # Generate secure random token
        invitation_token = secrets.token_urlsafe(32)

        # Create invitation
        invitation_in = WorkspaceInvitationCreate(
            workspace_id=workspace_id,
            email=email.lower(),  # Normalize to lowercase
            role=role,
            invitation_token=invitation_token,
            invited_by=inviter_id,
            expires_at=datetime.utcnow() + timedelta(days=7),  # 7-day expiration
            status='pending'
        )
        invitation = self.invitation_dao.create(session, obj_in=invitation_in)

        # Log event
        self.audit_dao.log_action(
            session,
            workspace_id=workspace_id,
            user_id=inviter_id,
            action='invitation_sent',
            metadata={'email': email, 'role': role}
        )

        return invitation

    def validate_invitation_for_user(
        self,
        session: Session,
        invitation_token: str,
        user_email: str
    ) -> WorkspaceInvitation:
        """
        Validate invitation can be accepted by user.

        Business rules (CRITICAL for security):
        - Token must exist
        - Not expired (7-day window)
        - Status must be 'pending'
        - user_email must match invitation.email (EMAIL MATCHING!)

        Args:
            session: Database session
            invitation_token: Invitation token from URL
            user_email: Email of user trying to accept

        Returns:
            Valid invitation

        Raises:
            ValueError: If validation fails

        Note:
            This is a READ operation (no flush needed)
        """
        # Get invitation by token
        invitation = self.invitation_dao.get_by_token(session, token=invitation_token)

        # Check 1: Token exists
        if not invitation:
            raise ValueError("Invalid invitation token")

        # Check 2: Not expired
        if invitation.expires_at < datetime.utcnow():
            raise ValueError("Invitation has expired. Please request a new invitation.")

        # Check 3: Still pending
        if invitation.status != 'pending':
            raise ValueError(f"Invitation has already been {invitation.status}")

        # Check 4: EMAIL MUST MATCH (CRITICAL SECURITY CHECK!)
        if invitation.email.lower() != user_email.lower():
            raise ValueError(
                f"This invitation was sent to {invitation.email}. "
                f"You cannot accept it with {user_email}."
            )

        return invitation

    def accept_invitation(
        self,
        session: Session,
        invitation_id: int,
        user_id: int
    ) -> WorkspaceMember:
        """
        Accept invitation and add user to workspace.

        Business logic:
        - Mark invitation as 'accepted'
        - Add user to workspace with invitation.role
        - Log acceptance event

        Args:
            session: Database session
            invitation_id: Invitation ID
            user_id: User accepting invitation

        Returns:
            Created workspace member (not yet committed)

        Note:
            This method does NOT commit. Service layer must commit.
            Should call validate_invitation_for_user BEFORE calling this.
        """
        invitation = self.invitation_dao.get(session, id=invitation_id)
        if not invitation:
            raise ValueError("Invitation not found")

        # Add user to workspace
        member = self.add_member_to_workspace(
            session=session,
            workspace_id=invitation.workspace_id,
            user_id=user_id,
            role=invitation.role,
            inviter_id=invitation.invited_by
        )

        # Update invitation status
        invitation.status = 'accepted'
        invitation.accepted_at = datetime.utcnow()
        invitation.accepted_by_user_id = user_id
        session.flush()

        # Log event
        self.audit_dao.log_action(
            session,
            workspace_id=invitation.workspace_id,
            user_id=user_id,
            action='invitation_accepted',
            metadata={'invitation_id': invitation_id}
        )

        return member

    def cancel_invitation(
        self,
        session: Session,
        invitation_id: int,
        canceller_id: int,
        canceller_role: str,
        workspace_id: int
    ) -> None:
        """
        Cancel pending invitation.

        Business rules:
        - Only owner/manager or original inviter can cancel
        - Can only cancel pending invitations

        Args:
            session: Database session
            invitation_id: Invitation to cancel
            canceller_id: User cancelling
            canceller_role: Role of canceller
            workspace_id: Workspace ID (for validation)

        Raises:
            ValueError: If validation fails

        Note:
            This method does NOT commit. Service layer must commit.
        """
        invitation = self.invitation_dao.get(session, id=invitation_id)
        if not invitation:
            raise ValueError("Invitation not found")

        if invitation.workspace_id != workspace_id:
            raise ValueError("Invitation does not belong to this workspace")

        if invitation.status != 'pending':
            raise ValueError(f"Cannot cancel invitation that is {invitation.status}")

        # Check permissions
        if canceller_role not in ['owner', 'ground-team-manager'] and canceller_id != invitation.invited_by:
            raise ValueError("You do not have permission to cancel this invitation")

        # Cancel invitation
        invitation.status = 'cancelled'
        session.flush()

        # Log event
        self.audit_dao.log_action(
            session,
            workspace_id=workspace_id,
            user_id=canceller_id,
            action='invitation_cancelled',
            metadata={'invitation_id': invitation_id, 'email': invitation.email}
        )


# Singleton instance
workspace_manager = WorkspaceManager()
