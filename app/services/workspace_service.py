"""Workspace Service for workspace management operations"""
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import List
import secrets
from app.services.base_service import BaseService
from app.dao.workspace import workspace_dao
from app.dao.workspace_member import workspace_member_dao
from app.dao.workspace_invitation import workspace_invitation_dao
from app.dao.workspace_audit_log import workspace_audit_log_dao
from app.dao.subscription_plan import subscription_plan_dao
from app.schemas.workspace import WorkspaceCreate, WorkspaceUpdate, WorkspaceListItem
from app.schemas.workspace_member import WorkspaceMemberCreate
from app.schemas.workspace_invitation import WorkspaceInvitationCreate, InviteUserRequest
from app.models.workspace import Workspace
from app.models.profile import Profile
from app.db.seed_default_statuses import seed_default_statuses
from app.db.seed_default_departments import seed_default_departments
from app.db.seed_default_tags import seed_default_tags
from app.db.seed_default_account_tags import seed_default_account_tags


class WorkspaceService(BaseService):
    """Service for workspace management workflows"""

    def create_workspace(
        self, db: Session, *, workspace_in: WorkspaceCreate, creator: Profile
    ) -> Workspace:
        """
        Create new workspace with creator as owner

        Args:
            db: Database session
            workspace_in: Workspace creation data
            creator: User creating the workspace

        Returns:
            Created workspace
        """
        try:
            # Get subscription plan (use provided or default)
            if workspace_in.subscription_plan_id:
                plan = subscription_plan_dao.get(db, id=workspace_in.subscription_plan_id)
                if not plan or not plan.is_active:
                    raise ValueError("Invalid subscription plan")
            else:
                plan = subscription_plan_dao.get_default_plan(db)
                if not plan:
                    raise ValueError("No default subscription plan found")

            # Create workspace
            workspace_data = workspace_in.model_dump(exclude={'subscription_plan_id'})
            workspace_data['subscription_plan_id'] = plan.id
            workspace_data['owner_user_id'] = creator.id
            workspace_data['created_by_user_id'] = creator.id
            workspace_data['trial_ends_at'] = datetime.utcnow() + timedelta(days=14)  # 14-day trial

            workspace = Workspace(**workspace_data)
            db.add(workspace)
            db.flush()

            # Add creator as owner member
            member_in = WorkspaceMemberCreate(
                workspace_id=workspace.id,
                user_id=creator.id,
                role='owner',
                status='active'
            )
            member_in.joined_at = datetime.utcnow()
            member = workspace_member_dao.create(db, obj_in=member_in)

            # Seed default data for workspace
            seed_default_statuses(db, workspace_id=workspace.id)
            seed_default_departments(db, workspace_id=workspace.id)
            seed_default_tags(db, workspace_id=workspace.id, created_by_user_id=creator.id)
            seed_default_account_tags(db, workspace_id=workspace.id, created_by_user_id=creator.id)

            # Log workspace creation
            workspace_audit_log_dao.log_action(
                db,
                workspace_id=workspace.id,
                user_id=creator.id,
                action='workspace_created',
                metadata={'plan': plan.name}
            )

            self._commit_transaction(db)
            db.refresh(workspace)
            return workspace

        except Exception as e:
            self._rollback_transaction(db)
            raise

    def get_user_workspaces(
        self, db: Session, *, user_id: int
    ) -> List[WorkspaceListItem]:
        """
        Get all workspaces user belongs to

        Args:
            user_id: User ID

        Returns:
            List of workspaces with user's role
        """
        memberships = workspace_member_dao.get_user_workspaces(db, user_id=user_id)

        workspaces = []
        for membership in memberships:
            workspace = workspace_dao.get(db, id=membership.workspace_id)
            if workspace:
                workspaces.append(
                    WorkspaceListItem(
                        id=workspace.id,
                        name=workspace.name,
                        slug=workspace.slug,
                        subscription_status=workspace.subscription_status,
                        role=membership.role,
                        is_owner=(workspace.owner_user_id == user_id)
                    )
                )

        return workspaces

    def invite_user(
        self,
        db: Session,
        *,
        workspace_id: int,
        invite_request: InviteUserRequest,
        inviter: Profile
    ) -> str:
        """
        Invite user to workspace

        Args:
            workspace_id: Workspace ID
            invite_request: Invitation details (email, role)
            inviter: User sending invitation

        Returns:
            Invitation token
        """
        try:
            # Check if user is already a member
            # (Would need to query profiles by email first, but simplified for now)
            existing_invite = workspace_invitation_dao.get_by_workspace_and_email(
                db, workspace_id=workspace_id, email=invite_request.email
            )

            if existing_invite and existing_invite.status == 'pending':
                raise ValueError("User already has a pending invitation")

            # Generate unique token
            token = secrets.token_urlsafe(32)

            # Create invitation
            invitation_in = WorkspaceInvitationCreate(
                workspace_id=workspace_id,
                email=invite_request.email,
                role=invite_request.role
            )

            invitation_data = invitation_in.model_dump()
            invitation_data['invited_by_user_id'] = inviter.id
            invitation_data['token'] = token
            invitation_data['expires_at'] = datetime.utcnow() + timedelta(days=7)  # 7-day expiry

            from app.models.workspace_invitation import WorkspaceInvitation
            invitation = WorkspaceInvitation(**invitation_data)
            db.add(invitation)
            db.flush()

            # Log invitation
            workspace_audit_log_dao.log_action(
                db,
                workspace_id=workspace_id,
                user_id=inviter.id,
                action='member_invited',
                metadata={'email': invite_request.email, 'role': invite_request.role}
            )

            self._commit_transaction(db)
            return token

        except Exception as e:
            self._rollback_transaction(db)
            raise

    def accept_invitation(
        self, db: Session, *, token: str, user: Profile
    ) -> Workspace:
        """
        Accept workspace invitation

        Args:
            token: Invitation token
            user: User accepting invitation

        Returns:
            Workspace user joined
        """
        try:
            # Get invitation
            invitation = workspace_invitation_dao.get_by_token(db, token=token)
            if not invitation:
                raise ValueError("Invalid invitation token")

            if invitation.status != 'pending':
                raise ValueError("Invitation is no longer valid")

            if invitation.expires_at < datetime.utcnow():
                workspace_invitation_dao.mark_as_expired(db, invitation=invitation)
                raise ValueError("Invitation has expired")

            # Check if user email matches
            if user.email != invitation.email:
                raise ValueError("This invitation is for a different email address")

            # Add user to workspace
            member_in = WorkspaceMemberCreate(
                workspace_id=invitation.workspace_id,
                user_id=user.id,
                role=invitation.role,
                invited_by_user_id=invitation.invited_by_user_id,
                status='active'
            )
            member_data = member_in.model_dump()
            member_data['joined_at'] = datetime.utcnow()

            from app.models.workspace_member import WorkspaceMember
            member = WorkspaceMember(**member_data)
            db.add(member)
            db.flush()

            # Mark invitation as accepted
            workspace_invitation_dao.mark_as_accepted(db, invitation=invitation)

            # Increment member count
            workspace_dao.increment_usage(
                db, workspace_id=invitation.workspace_id, field='members'
            )

            # Log action
            workspace_audit_log_dao.log_action(
                db,
                workspace_id=invitation.workspace_id,
                user_id=user.id,
                action='member_joined',
                metadata={'role': invitation.role}
            )

            self._commit_transaction(db)

            workspace = workspace_dao.get(db, id=invitation.workspace_id)
            return workspace

        except Exception as e:
            self._rollback_transaction(db)
            raise

    def change_member_role(
        self,
        db: Session,
        *,
        workspace_id: int,
        user_id: int,
        new_role: str,
        changer: Profile
    ) -> None:
        """
        Change user's role in workspace

        Args:
            workspace_id: Workspace ID
            user_id: User ID whose role to change
            new_role: New role
            changer: User making the change
        """
        try:
            # Get member
            member = workspace_member_dao.get_by_workspace_and_user(
                db, workspace_id=workspace_id, user_id=user_id
            )
            if not member:
                raise ValueError("User is not a member of this workspace")

            old_role = member.role

            # Update role
            workspace_member_dao.update_role(
                db, workspace_id=workspace_id, user_id=user_id, new_role=new_role
            )

            # Log action
            workspace_audit_log_dao.log_action(
                db,
                workspace_id=workspace_id,
                user_id=changer.id,
                action='role_changed',
                resource_type='member',
                resource_id=user_id,
                metadata={'old_role': old_role, 'new_role': new_role}
            )

            self._commit_transaction(db)

        except Exception as e:
            self._rollback_transaction(db)
            raise

    def remove_member(
        self,
        db: Session,
        *,
        workspace_id: int,
        user_id: int,
        remover: Profile
    ) -> None:
        """
        Remove user from workspace

        Args:
            workspace_id: Workspace ID
            user_id: User ID to remove
            remover: User removing the member
        """
        try:
            # Get workspace
            workspace = workspace_dao.get(db, id=workspace_id)
            if not workspace:
                raise ValueError("Workspace not found")

            # Cannot remove workspace owner
            if workspace.owner_user_id == user_id:
                raise ValueError("Cannot remove workspace owner")

            # Get member
            member = workspace_member_dao.get_by_workspace_and_user(
                db, workspace_id=workspace_id, user_id=user_id
            )
            if not member:
                raise ValueError("User is not a member of this workspace")

            # Remove member
            db.delete(member)
            db.flush()

            # Decrement member count
            workspace_dao.decrement_usage(db, workspace_id=workspace_id, field='members')

            # Log action
            workspace_audit_log_dao.log_action(
                db,
                workspace_id=workspace_id,
                user_id=remover.id,
                action='member_removed',
                resource_type='member',
                resource_id=user_id,
                metadata={'removed_user_role': member.role}
            )

            self._commit_transaction(db)

        except Exception as e:
            self._rollback_transaction(db)
            raise

    def update_workspace(
        self,
        db: Session,
        *,
        workspace_id: int,
        workspace_update: WorkspaceUpdate,
        updater: Profile
    ) -> Workspace:
        """
        Update workspace settings

        Args:
            workspace_id: Workspace ID
            workspace_update: Update data
            updater: User updating workspace

        Returns:
            Updated workspace
        """
        try:
            workspace = workspace_dao.get(db, id=workspace_id)
            if not workspace:
                raise ValueError("Workspace not found")

            # Update workspace
            workspace = workspace_dao.update(db, db_obj=workspace, obj_in=workspace_update)

            # Log action
            workspace_audit_log_dao.log_action(
                db,
                workspace_id=workspace_id,
                user_id=updater.id,
                action='workspace_updated',
                metadata=workspace_update.model_dump(exclude_unset=True)
            )

            self._commit_transaction(db)
            db.refresh(workspace)
            return workspace

        except Exception as e:
            self._rollback_transaction(db)
            raise


workspace_service = WorkspaceService()
