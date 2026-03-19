"""Authentication Service for user registration, login, and password management"""
from typing import Tuple, Dict, Any, Optional
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import secrets
from app.services.base_service import BaseService
from app.managers.workspace_manager import workspace_manager
from app.dao.profile import profile_dao
from app.dao.workspace import workspace_dao
from app.dao.workspace_member import workspace_member_dao
from app.dao.workspace_invitation import workspace_invitation_dao
from app.dao.subscription_plan import subscription_plan_dao
from app.schemas.profile import ProfileCreate
from app.schemas.workspace import WorkspaceCreate
from app.models.profile import Profile
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember
from app.core.security import create_access_token, get_password_hash, verify_password
from app.core.exceptions import NotFoundError
from app.schemas.response import ActionMessage, success_message, error_message, info_message


class AuthService(BaseService):
    """
    Service for Authentication workflows.

    Handles:
    - User registration (with or without workspace)
    - Login and token generation
    - Invitation acceptance
    - Password reset (forgot password flow)
    - Admin password reset
    - Transaction boundaries (commit/rollback)
    """

    def __init__(self):
        super().__init__()
        self.workspace_manager = workspace_manager
        self.profile_dao = profile_dao
        self.workspace_dao = workspace_dao
        self.workspace_member_dao = workspace_member_dao
        self.workspace_invitation_dao = workspace_invitation_dao
        self.subscription_dao = subscription_plan_dao

    # ============================================================================
    # REGISTRATION WORKFLOWS
    # ============================================================================

    def register_user(
        self,
        db: Session,
        name: str,
        email: str,
        password: str,
        position: str = "User",
        workspace_name: Optional[str] = None,
        invitation_token: Optional[str] = None
    ) -> Tuple[Profile, Workspace, str, list[ActionMessage]]:
        """
        Register new user with workspace creation OR invitation acceptance.

        Two paths:
        1. Create new workspace: workspace_name provided, invitation_token is None
        2. Accept invitation: invitation_token provided, workspace_name optional (ignored)

        Business rules:
        - Email must be unique
        - Either workspace_name OR invitation_token required (not both)
        - If invitation: email must match invitation email
        - If invitation: workspace and role determined by invitation

        Args:
            db: Database session
            name: User's full name
            email: User's email
            password: User's password (will be hashed)
            position: User's position/title
            workspace_name: Name for new workspace (if creating)
            invitation_token: Invitation token (if accepting invite)

        Returns:
            Tuple of (user, workspace, jwt_token, messages)

        Raises:
            ValueError: If validation fails

        Note:
            This method commits the transaction.
        """
        messages = []

        try:
            # Validate: email not already registered
            existing_user = self.profile_dao.get_by_email(db, email=email)
            if existing_user:
                raise ValueError(f"Email {email} is already registered")

            # Validate: must provide either workspace_name or invitation_token
            if not workspace_name and not invitation_token:
                raise ValueError("Must provide either workspace_name (to create workspace) or invitation_token (to join workspace)")

            # PATH 1: Accept Invitation
            if invitation_token:
                user, workspace, jwt_token, invite_messages = self._register_with_invitation(
                    db=db,
                    name=name,
                    email=email,
                    password=password,
                    position=position,
                    invitation_token=invitation_token
                )
                messages.extend(invite_messages)

            # PATH 2: Create New Workspace
            else:
                user, workspace, jwt_token, workspace_messages = self._register_with_new_workspace(
                    db=db,
                    name=name,
                    email=email,
                    password=password,
                    position=position,
                    workspace_name=workspace_name
                )
                messages.extend(workspace_messages)

            # Commit transaction
            self._commit_transaction(db)
            db.refresh(user)
            db.refresh(workspace)

            messages.append(success_message(
                f"Welcome {name}! Your account has been created successfully."
            ))

            return user, workspace, jwt_token, messages

        except Exception as e:
            self._rollback_transaction(db)
            raise

    def _register_with_invitation(
        self,
        db: Session,
        name: str,
        email: str,
        password: str,
        position: str,
        invitation_token: str
    ) -> Tuple[Profile, Workspace, str, list[ActionMessage]]:
        """
        Register user by accepting workspace invitation.

        Steps:
        1. Validate invitation (email matching, expiration, status)
        2. Create user profile
        3. Accept invitation (adds user to workspace)
        4. Generate JWT token

        Returns:
            Tuple of (user, workspace, jwt_token, messages)
        """
        messages = []

        # Validate invitation using workspace manager
        invitation = self.workspace_manager.validate_invitation_for_user(
            session=db,
            invitation_token=invitation_token,
            user_email=email
        )

        messages.append(info_message(
            f"Valid invitation found for workspace: {invitation.workspace.name}"
        ))

        # Create user profile
        profile_in = ProfileCreate(
            name=name,
            email=email,
            password=password,
            position=position,
            permission='ground-team'  # Default role, will be overridden by invitation.role
        )
        user = self.profile_dao.create(db, obj_in=profile_in)
        db.flush()  # Get user.id

        messages.append(success_message("User profile created"))

        # Accept invitation (adds user to workspace with correct role)
        self.workspace_manager.accept_invitation(
            session=db,
            invitation_id=invitation.id,
            user_id=user.id
        )

        # Get workspace
        workspace = self.workspace_dao.get(db, id=invitation.workspace_id)

        messages.append(success_message(
            f"You've been added to workspace '{workspace.name}' with role '{invitation.role}'"
        ))

        # Generate JWT token
        jwt_token = create_access_token(
            data={
                "sub": str(user.id),
                "email": user.email,
                "workspace_id": workspace.id
            }
        )

        return user, workspace, jwt_token, messages

    def _register_with_new_workspace(
        self,
        db: Session,
        name: str,
        email: str,
        password: str,
        position: str,
        workspace_name: str
    ) -> Tuple[Profile, Workspace, str, list[ActionMessage]]:
        """
        Register user and create new workspace.

        Steps:
        1. Create user profile
        2. Create workspace with user as owner
        3. Generate JWT token

        Returns:
            Tuple of (user, workspace, jwt_token, messages)
        """
        messages = []

        # Create user profile
        profile_in = ProfileCreate(
            name=name,
            email=email,
            password=password,
            position=position,
            permission='owner'  # Owner of their own workspace
        )
        user = self.profile_dao.create(db, obj_in=profile_in)
        db.flush()  # Get user.id

        messages.append(success_message("User profile created"))

        # Generate workspace slug from name
        slug = workspace_name.lower().replace(' ', '-').replace('_', '-')
        # Remove any non-alphanumeric characters except hyphens
        slug = ''.join(c for c in slug if c.isalnum() or c == '-')
        # Remove consecutive hyphens
        while '--' in slug:
            slug = slug.replace('--', '-')
        slug = slug.strip('-')

        # Create workspace with user as owner
        workspace_data = WorkspaceCreate(
            name=workspace_name,
            slug=slug,
            billing_email=email,
            subscription_plan_id=None  # Will use default plan
        )

        workspace = self.workspace_manager.create_workspace_with_owner(
            session=db,
            workspace_data=workspace_data,
            owner_user_id=user.id,
            subscription_plan_id=None  # Use default plan
        )

        messages.append(success_message(
            f"Workspace '{workspace_name}' created successfully with 14-day trial"
        ))

        # Generate JWT token
        jwt_token = create_access_token(
            data={
                "sub": str(user.id),
                "email": user.email,
                "workspace_id": workspace.id
            }
        )

        return user, workspace, jwt_token, messages

    # ============================================================================
    # LOGIN WORKFLOWS
    # ============================================================================

    def login_user(
        self,
        db: Session,
        email: str,
        password: str
    ) -> Tuple[Profile, str, list[ActionMessage]]:
        """
        Authenticate user and generate JWT token (WITHOUT workspace).

        Business rules:
        - Email and password must match
        - User must be active
        - User selects workspace AFTER login via GET /workspaces

        Args:
            db: Database session
            email: User's email
            password: User's password

        Returns:
            Tuple of (user, jwt_token, messages)

        Raises:
            ValueError: If authentication fails

        Note:
            This is a read-only operation (no commit needed).
            Frontend should call GET /workspaces after login to let user select workspace.
        """
        messages = []

        # Authenticate user
        user = self.profile_dao.authenticate(db, email=email, password=password)
        if not user:
            raise ValueError("Invalid email or password")

        # Check if user is active (assuming profile has is_active field)
        # If not, you can skip this check
        # if hasattr(user, 'is_active') and not user.is_active:
        #     raise ValueError("Account is inactive. Please contact support.")

        messages.append(success_message(f"Welcome back, {user.name}!"))

        # Generate JWT token WITHOUT workspace (user will select workspace after login)
        jwt_token = create_access_token(
            data={
                "sub": str(user.id),
                "email": user.email
            }
        )

        return user, jwt_token, messages

    def switch_workspace(
        self,
        db: Session,
        user_id: int,
        workspace_id: int
    ) -> Tuple[Workspace, str, list[ActionMessage]]:
        """
        Switch user to a different workspace.

        Business rules:
        - User must be active member of target workspace

        Args:
            db: Database session
            user_id: User ID
            workspace_id: Target workspace ID

        Returns:
            Tuple of (workspace, jwt_token, messages)

        Raises:
            ValueError: If user is not member of workspace

        Note:
            This is a read-only operation (no commit needed)
        """
        messages = []

        # Verify membership
        membership = self.workspace_member_dao.get_by_workspace_and_user(
            db, workspace_id=workspace_id, user_id=user_id
        )
        if not membership or membership.status != 'active':
            raise ValueError("You are not a member of this workspace")

        workspace = self.workspace_dao.get(db, id=workspace_id)
        if not workspace:
            raise ValueError("Workspace not found")

        # Get user for token
        user = self.profile_dao.get(db, id=user_id)

        # Generate new JWT token with new workspace
        jwt_token = create_access_token(
            data={
                "sub": str(user.id),
                "email": user.email,
                "workspace_id": workspace.id
            }
        )

        messages.append(success_message(f"Switched to workspace: {workspace.name}"))

        return workspace, jwt_token, messages

    # ============================================================================
    # PASSWORD MANAGEMENT
    # ============================================================================

    def request_password_reset(
        self,
        db: Session,
        email: str
    ) -> Tuple[str, datetime, list[ActionMessage]]:
        """
        Generate password reset token for user.

        Business rules:
        - User must exist
        - Token expires in 1 hour
        - Token is cryptographically secure random string

        Args:
            db: Database session
            email: User's email

        Returns:
            Tuple of (reset_token, expires_at, messages)

        Raises:
            ValueError: If user not found

        Note:
            TODO: This currently generates token but doesn't store it.
            We need a password_reset_tokens table to store:
            - user_id, token, expires_at, used (boolean)

            For now, you'll need to implement token storage separately
            or use a temporary cache (Redis).
        """
        messages = []

        # Get user
        user = self.profile_dao.get_by_email(db, email=email)
        if not user:
            # Security: Don't reveal if email exists or not
            # Return success message anyway
            messages.append(info_message(
                "If an account with that email exists, a password reset link has been sent."
            ))
            # Generate fake token to prevent timing attacks
            fake_token = secrets.token_urlsafe(32)
            fake_expires = datetime.utcnow() + timedelta(hours=1)
            return fake_token, fake_expires, messages

        # Generate secure token
        reset_token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(hours=1)

        # TODO: Store token in database
        # For now, just return the token (caller must store it)
        # Example:
        # password_reset_dao.create(db, obj_in={
        #     'user_id': user.id,
        #     'token': reset_token,
        #     'expires_at': expires_at,
        #     'used': False
        # })
        # db.flush()

        messages.append(success_message(
            f"Password reset token generated for {email}. Token expires in 1 hour."
        ))
        messages.append(info_message(
            "NOTE: Token storage not yet implemented. Store this token securely and validate on reset."
        ))

        return reset_token, expires_at, messages

    def reset_password(
        self,
        db: Session,
        reset_token: str,
        new_password: str
    ) -> Tuple[Profile, list[ActionMessage]]:
        """
        Reset user password using reset token.

        Business rules:
        - Token must be valid and not expired
        - Token can only be used once
        - Password will be hashed

        Args:
            db: Database session
            reset_token: Password reset token
            new_password: New password (plain text)

        Returns:
            Tuple of (user, messages)

        Raises:
            ValueError: If token invalid or expired

        Note:
            TODO: This needs a password_reset_tokens table to validate tokens.
            For now, it's a placeholder implementation.
        """
        messages = []

        # TODO: Validate token from database
        # token_record = password_reset_dao.get_by_token(db, token=reset_token)
        # if not token_record:
        #     raise ValueError("Invalid or expired reset token")
        # if token_record.used:
        #     raise ValueError("Reset token has already been used")
        # if token_record.expires_at < datetime.utcnow():
        #     raise ValueError("Reset token has expired")

        # For now, raise not implemented error
        raise NotImplementedError(
            "Password reset requires a password_reset_tokens table. "
            "Please implement password_reset model, DAO, and schema first."
        )

        # TODO: Once table exists, implement:
        # user = self.profile_dao.get(db, id=token_record.user_id)
        # user.hashed_password = get_password_hash(new_password)
        # token_record.used = True
        # db.flush()
        # self._commit_transaction(db)
        # messages.append(success_message("Password reset successfully"))
        # return user, messages

    def reset_password_by_admin(
        self,
        db: Session,
        admin_user_id: int,
        target_user_id: int,
        new_password: str,
        workspace_id: int
    ) -> Tuple[Profile, list[ActionMessage]]:
        """
        Admin resets another user's password.

        Business rules:
        - Admin must be owner or have admin permissions
        - Target user must be in same workspace
        - Cannot reset owner's password unless you are owner

        Args:
            db: Database session
            admin_user_id: Admin user performing reset
            target_user_id: User whose password to reset
            new_password: New password (plain text)
            workspace_id: Workspace context

        Returns:
            Tuple of (target_user, messages)

        Raises:
            ValueError: If validation fails

        Note:
            This method commits the transaction.
        """
        messages = []

        try:
            # Verify admin is member of workspace
            admin_membership = self.workspace_member_dao.get_by_workspace_and_user(
                db, workspace_id=workspace_id, user_id=admin_user_id
            )
            if not admin_membership or admin_membership.status != 'active':
                raise ValueError("Admin is not a member of this workspace")

            # Verify admin has owner role (only owners can reset passwords)
            if admin_membership.role != 'owner':
                raise ValueError("Only workspace owners can reset user passwords")

            # Verify target user is member of workspace
            target_membership = self.workspace_member_dao.get_by_workspace_and_user(
                db, workspace_id=workspace_id, user_id=target_user_id
            )
            if not target_membership or target_membership.status != 'active':
                raise ValueError("Target user is not a member of this workspace")

            # Get target user
            target_user = self.profile_dao.get(db, id=target_user_id)
            if not target_user:
                raise ValueError("Target user not found")

            # Update password
            target_user.hashed_password = get_password_hash(new_password)
            db.flush()

            # Commit transaction
            self._commit_transaction(db)

            messages.append(success_message(
                f"Password reset successfully for user: {target_user.email}"
            ))
            messages.append(info_message(
                "User should be notified of password change via email."
            ))

            return target_user, messages

        except Exception as e:
            self._rollback_transaction(db)
            raise

    # ============================================================================
    # UTILITY METHODS
    # ============================================================================

    def validate_invitation_token(
        self,
        db: Session,
        invitation_token: str
    ) -> Tuple[Dict[str, Any], list[ActionMessage]]:
        """
        Validate invitation token without accepting it.

        Useful for showing invitation details before user registers.

        Args:
            db: Database session
            invitation_token: Invitation token

        Returns:
            Tuple of (invitation_details, messages)

        Raises:
            ValueError: If token invalid

        Note:
            This is a read-only operation (no commit needed)
        """
        messages = []

        # Get invitation by token
        invitation = self.workspace_invitation_dao.get_by_token(db, token=invitation_token)

        if not invitation:
            raise ValueError("Invalid invitation token")

        # Check expiration
        if invitation.expires_at < datetime.utcnow():
            raise ValueError("Invitation has expired. Please request a new invitation.")

        # Check status
        if invitation.status != 'pending':
            raise ValueError(f"Invitation has already been {invitation.status}")

        # Get workspace details
        workspace = self.workspace_dao.get(db, id=invitation.workspace_id)

        # Get inviter details
        inviter = None
        if invitation.invited_by:
            inviter = self.profile_dao.get(db, id=invitation.invited_by)

        details = {
            'invitation_id': invitation.id,
            'email': invitation.email,
            'role': invitation.role,
            'workspace_id': workspace.id,
            'workspace_name': workspace.name,
            'inviter_name': inviter.name if inviter else None,
            'expires_at': invitation.expires_at.isoformat()
        }

        messages.append(success_message(
            f"Valid invitation to join '{workspace.name}' as {invitation.role}"
        ))

        return details, messages


# Singleton instance
auth_service = AuthService()
