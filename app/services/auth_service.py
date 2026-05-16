"""Authentication Service for user registration, login, and password management"""
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Tuple, Dict, Any, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    get_password_hash,
    hash_refresh_token,
    verify_password,
)
from app.dao.profile import profile_dao
from app.dao.refresh_token import refresh_token_dao
from app.dao.subscription_plan import subscription_plan_dao
from app.dao.workspace import workspace_dao
from app.dao.workspace_invitation import workspace_invitation_dao
from app.dao.workspace_member import workspace_member_dao
from app.managers.workspace_manager import workspace_manager
from app.models.profile import Profile
from app.models.refresh_token import RefreshToken
from app.models.workspace import Workspace
from app.models.workspace_member import WorkspaceMember
from app.schemas.profile import ProfileCreate
from app.schemas.response import ActionMessage, success_message, error_message, info_message
from app.schemas.workspace import WorkspaceCreate


@dataclass
class TokenPair:
    """Internal result type returned by `_issue_token_pair`.

    The raw refresh token is the value handed to the client; only its hash is
    stored. `expires_in` / `refresh_expires_in` are in seconds.
    """
    access_token: str
    refresh_token: str
    expires_in: int
    refresh_expires_in: int


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
        self.refresh_token_dao = refresh_token_dao

    # ============================================================================
    # TOKEN ISSUANCE HELPERS
    # ============================================================================

    def _issue_token_pair(
        self,
        db: Session,
        *,
        user: Profile,
        workspace_id: Optional[int],
        family_id: Optional[str] = None,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> TokenPair:
        """Mint an (access_token, refresh_token) pair and persist the refresh row.

        Args:
            user:          authenticated user.
            workspace_id:  optional — included in the access-token JWT claim,
                           and stored on the refresh-token row for diagnostics.
                           May be None when the user hasn't picked a workspace yet
                           (immediately after `/auth/login/`).
            family_id:     when continuing an existing rotation chain (e.g. on
                           `/auth/refresh/`), the caller passes the same family.
                           Pass None for fresh logins to start a new family.
            user_agent / ip_address: best-effort diagnostics for "active sessions".

        Does NOT commit. Caller is responsible.
        """
        access_claims: Dict[str, Any] = {
            "sub": str(user.id),
            "email": user.email,
        }
        if workspace_id is not None:
            access_claims["workspace_id"] = workspace_id

        access_token = create_access_token(data=access_claims)

        raw_refresh, refresh_hash = create_refresh_token()
        expires_at = datetime.utcnow() + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )

        self.refresh_token_dao.create(
            db,
            user_id=user.id,
            workspace_id=workspace_id,
            token_hash=refresh_hash,
            family_id=family_id or uuid.uuid4().hex,
            expires_at=expires_at,
            user_agent=user_agent,
            ip_address=ip_address,
        )

        return TokenPair(
            access_token=access_token,
            refresh_token=raw_refresh,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            refresh_expires_in=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        )

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
        invitation_token: Optional[str] = None,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> Tuple[Profile, Workspace, TokenPair, list[ActionMessage]]:
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
                user, workspace, token_pair, invite_messages = self._register_with_invitation(
                    db=db,
                    name=name,
                    email=email,
                    password=password,
                    position=position,
                    invitation_token=invitation_token,
                    user_agent=user_agent,
                    ip_address=ip_address,
                )
                messages.extend(invite_messages)

            # PATH 2: Create New Workspace
            else:
                user, workspace, token_pair, workspace_messages = self._register_with_new_workspace(
                    db=db,
                    name=name,
                    email=email,
                    password=password,
                    position=position,
                    workspace_name=workspace_name,
                    user_agent=user_agent,
                    ip_address=ip_address,
                )
                messages.extend(workspace_messages)

            # Commit transaction
            self._commit_transaction(db)
            db.refresh(user)
            db.refresh(workspace)

            messages.append(success_message(
                f"Welcome {name}! Your account has been created successfully."
            ))

            return user, workspace, token_pair, messages

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
        invitation_token: str,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> Tuple[Profile, Workspace, TokenPair, list[ActionMessage]]:
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

        # Issue access + refresh token pair (new family, workspace already
        # known because invitation determines membership).
        token_pair = self._issue_token_pair(
            db,
            user=user,
            workspace_id=workspace.id,
            user_agent=user_agent,
            ip_address=ip_address,
        )

        return user, workspace, token_pair, messages

    def _register_with_new_workspace(
        self,
        db: Session,
        name: str,
        email: str,
        password: str,
        position: str,
        workspace_name: str,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> Tuple[Profile, Workspace, TokenPair, list[ActionMessage]]:
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

        # Issue access + refresh token pair (new family).
        token_pair = self._issue_token_pair(
            db,
            user=user,
            workspace_id=workspace.id,
            user_agent=user_agent,
            ip_address=ip_address,
        )

        return user, workspace, token_pair, messages

    # ============================================================================
    # LOGIN WORKFLOWS
    # ============================================================================

    def login_user(
        self,
        db: Session,
        email: str,
        password: str,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> Tuple[Profile, TokenPair, list[ActionMessage]]:
        """
        Authenticate user and issue an access + refresh token pair (no workspace
        claim — user picks workspace next via `/auth/switch-workspace/`).

        This method DOES commit because it inserts a refresh-token row.
        """
        messages = []

        # Authenticate user
        user = self.profile_dao.authenticate(db, email=email, password=password)
        if not user:
            raise ValueError("Invalid email or password")

        messages.append(success_message(f"Welcome back, {user.name}!"))

        try:
            # New rotation family; no workspace selected yet.
            token_pair = self._issue_token_pair(
                db,
                user=user,
                workspace_id=None,
                user_agent=user_agent,
                ip_address=ip_address,
            )
            self._commit_transaction(db)
        except Exception:
            self._rollback_transaction(db)
            raise

        return user, token_pair, messages

    def switch_workspace(
        self,
        db: Session,
        user_id: int,
        workspace_id: int,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> Tuple[Workspace, TokenPair, list[ActionMessage]]:
        """
        Switch user to a different workspace.

        Issues a brand-new token pair (with a new family) reflecting the new
        workspace. The caller's previous refresh token is NOT revoked here —
        if the client still holds it, it remains valid until expiry or until
        the user logs out. We don't try to identify "the previous session"
        because switch is also reachable from a freshly-restored client where
        the in-memory refresh token may differ from what's on disk.

        This method commits (inserts a refresh-token row).
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

        user = self.profile_dao.get(db, id=user_id)

        try:
            token_pair = self._issue_token_pair(
                db,
                user=user,
                workspace_id=workspace.id,
                user_agent=user_agent,
                ip_address=ip_address,
            )
            self._commit_transaction(db)
        except Exception:
            self._rollback_transaction(db)
            raise

        messages.append(success_message(f"Switched to workspace: {workspace.name}"))

        return workspace, token_pair, messages

    # ============================================================================
    # REFRESH + LOGOUT FLOWS
    # ============================================================================

    def refresh_access_token(
        self,
        db: Session,
        raw_refresh_token: str,
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> Tuple[TokenPair, list[ActionMessage]]:
        """Exchange a refresh token for a fresh access + refresh pair.

        Rotation + reuse-detection rules:
        - If the presented token doesn't exist → 401 (unknown).
        - If it exists, is revoked, AND has a `replaced_by_id` → that means a
          rotated-out token is being replayed. Likely theft. Revoke the entire
          family and refuse.
        - If revoked or expired (without replaced_by_id) → 401 (just denied).
        - Otherwise: revoke this row, point `replaced_by_id` at the new row,
          and issue (access, refresh) with the same `family_id`.

        Workspace claim on the new access token comes from the refresh row's
        `workspace_id` — that's the workspace the session was issued for.

        Raises:
            ValueError on any reject condition (caller maps to HTTP 401).
        """
        messages = []

        token_hash = hash_refresh_token(raw_refresh_token)
        row = self.refresh_token_dao.get_by_hash(db, token_hash=token_hash)

        try:
            if row is None:
                raise ValueError("Invalid refresh token")

            # --- Reuse detection ---
            if row.revoked_at is not None and row.replaced_by_id is not None:
                # A successor exists AND the original was already revoked, but
                # the original is being presented again. Treat as theft.
                self.refresh_token_dao.revoke_family(db, family_id=row.family_id)
                self._commit_transaction(db)
                raise ValueError(
                    "Refresh token reuse detected; all sessions for this login have been revoked"
                )

            # --- Plain rejection cases ---
            if row.revoked_at is not None:
                raise ValueError("Refresh token has been revoked")
            if row.expires_at <= datetime.utcnow():
                raise ValueError("Refresh token has expired")

            # --- Healthy path: rotate ---
            user = self.profile_dao.get(db, id=row.user_id)
            if not user:
                raise ValueError("User no longer exists")

            workspace_id = row.workspace_id  # may be None pre-workspace-pick

            new_pair = self._issue_token_pair(
                db,
                user=user,
                workspace_id=workspace_id,
                family_id=row.family_id,
                user_agent=user_agent,
                ip_address=ip_address,
            )
            # Look up the just-created row so we can link old.replaced_by_id.
            new_row = self.refresh_token_dao.get_by_hash(
                db, token_hash=hash_refresh_token(new_pair.refresh_token)
            )
            self.refresh_token_dao.revoke(
                db, row=row, replaced_by_id=new_row.id if new_row else None
            )
            self.refresh_token_dao.touch_last_used(db, row=row)

            self._commit_transaction(db)
            return new_pair, messages

        except ValueError:
            self._rollback_transaction(db)
            raise
        except Exception:
            self._rollback_transaction(db)
            raise

    def logout_session(
        self,
        db: Session,
        raw_refresh_token: Optional[str],
        user_id: Optional[int] = None,
        all_devices: bool = False,
    ) -> list[ActionMessage]:
        """Revoke either the presented refresh token, or every active refresh
        token for the user (when `all_devices=True`).

        Best-effort: missing / already-revoked tokens are not an error — the
        net effect is "the client is logged out".

        `user_id` is required when `all_devices=True` (we need to know whom).
        """
        messages = []

        try:
            if all_devices:
                if user_id is None:
                    raise ValueError(
                        "Cannot logout all devices without an authenticated user"
                    )
                count = self.refresh_token_dao.revoke_all_for_user(
                    db, user_id=user_id
                )
                messages.append(success_message(
                    f"Revoked {count} active session(s)."
                ))
            elif raw_refresh_token:
                token_hash = hash_refresh_token(raw_refresh_token)
                row = self.refresh_token_dao.get_by_hash(db, token_hash=token_hash)
                if row and row.revoked_at is None:
                    self.refresh_token_dao.revoke(db, row=row)
                # Silently succeed even if unknown/already revoked.
                messages.append(success_message("Logged out."))
            else:
                messages.append(info_message("No refresh token provided; nothing to revoke."))

            self._commit_transaction(db)
            return messages
        except Exception:
            self._rollback_transaction(db)
            raise

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

            # SECURITY: invalidate every active session for this user so a
            # leaked/old password can't keep a stolen refresh token alive.
            revoked = self.refresh_token_dao.revoke_all_for_user(
                db, user_id=target_user_id
            )

            # Commit transaction
            self._commit_transaction(db)

            messages.append(success_message(
                f"Password reset successfully for user: {target_user.email}"
            ))
            if revoked:
                messages.append(info_message(
                    f"Revoked {revoked} active session(s); user must log in again."
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
