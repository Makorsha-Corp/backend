"""
Authentication endpoints

Provides comprehensive authentication:
- User registration (with workspace creation or invitation acceptance)
- Login with workspace selection
- Workspace switching
- Password reset (forgot password flow)
- Admin password reset
- Invitation validation
"""
from datetime import timedelta
from typing import Optional, Tuple

from fastapi import APIRouter, Depends, Request, status, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_active_user, get_current_workspace
from app.core.config import settings
from app.core.exceptions import ConflictError, AuthenticationError, NotFoundError
from app.schemas.auth import (
    RegisterRequest,
    RegisterResponse,
    LoginRequest,
    LoginResponse,
    SwitchWorkspaceRequest,
    SwitchWorkspaceResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
    AdminResetPasswordRequest,
    AdminResetPasswordResponse,
    ValidateInvitationRequest,
    ValidateInvitationResponse,
    RefreshTokenRequest,
    TokenPair as TokenPairResponse,
    LogoutRequest,
)
from app.services.auth_service import auth_service
from app.models.profile import Profile
from app.models.workspace import Workspace


def _client_context(request: Request) -> Tuple[Optional[str], Optional[str]]:
    """Best-effort extraction of (user_agent, ip_address) for diagnostics.

    Stored on the refresh_tokens row so we can build an "active sessions" UI
    later. NOT used for any auth decision — never trust client-supplied data
    for security gates.
    """
    ua = request.headers.get("user-agent")
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    else:
        ip = request.client.host if request.client else None
    return ua, ip


router = APIRouter()


# ============================================================================
# REGISTRATION ENDPOINTS
# ============================================================================

@router.post(
    "/register/",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new user",
    description="""
    Register a new user with one of two paths:

    **Path 1: Create New Workspace**
    - Provide: name, email, password, workspace_name
    - Omit: invitation_token
    - Result: User created as owner of new workspace

    **Path 2: Accept Invitation**
    - Provide: name, email, password, invitation_token
    - Optional: workspace_name (ignored if invitation provided)
    - Result: User added to invited workspace with specified role

    Returns JWT token, user profile, and workspace details.
    """
)
def register(
    body: RegisterRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Register a new user.

    Either workspace_name OR invitation_token must be provided.
    Returns access token, refresh token, user, workspace, and messages.

    Raises:
        - 409 Conflict: Email already registered
        - 400 Bad Request: Validation errors
    """
    try:
        user_agent, ip_address = _client_context(request)
        user, workspace, token_pair, messages = auth_service.register_user(
            db=db,
            name=body.name,
            email=body.email,
            password=body.password,
            position=body.position,
            workspace_name=body.workspace_name,
            invitation_token=body.invitation_token,
            user_agent=user_agent,
            ip_address=ip_address,
        )

        return RegisterResponse(
            access_token=token_pair.access_token,
            refresh_token=token_pair.refresh_token,
            token_type="bearer",
            expires_in=token_pair.expires_in,
            refresh_expires_in=token_pair.refresh_expires_in,
            user={
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "permission": user.permission,
                "position": user.position
            },
            workspace={
                "id": workspace.id,
                "name": workspace.name,
                "slug": workspace.slug
            },
            messages=[msg.model_dump() for msg in messages]
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")


# ============================================================================
# LOGIN ENDPOINTS
# ============================================================================

@router.post(
    "/login/",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="User login (workspace selection separate)",
    description="""
    Authenticate user with email and password.

    **NEW FLOW (Jan 2025):**
    1. Login returns user + token (NO workspace)
    2. Call GET /workspaces to get user's workspaces
    3. User selects workspace from list
    4. Frontend stores workspace_id for subsequent API calls
    5. All protected endpoints require X-Workspace-ID header

    Returns JWT access token and user profile.
    Token should be sent in Authorization header as: `Bearer <token>`
    """
)
def login(
    credentials: LoginRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Login with email and password (workspace selection happens after).

    Returns:
        - access_token: short-lived JWT (sent in Authorization: Bearer <…>)
        - refresh_token: long-lived opaque credential used by POST /auth/refresh/
        - token_type: "bearer"
        - expires_in / refresh_expires_in: lifetimes in seconds
        - user: profile data
        - messages: informational messages

    Raises:
        - 401 Unauthorized: Invalid credentials
    """
    try:
        user_agent, ip_address = _client_context(request)
        user, token_pair, messages = auth_service.login_user(
            db=db,
            email=credentials.email,
            password=credentials.password,
            user_agent=user_agent,
            ip_address=ip_address,
        )

        return LoginResponse(
            access_token=token_pair.access_token,
            refresh_token=token_pair.refresh_token,
            token_type="bearer",
            expires_in=token_pair.expires_in,
            refresh_expires_in=token_pair.refresh_expires_in,
            user={
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "permission": user.permission,
                "position": user.position
            },
            messages=[msg.model_dump() for msg in messages]
        )

    except ValueError as e:
        # Invalid credentials or not member of workspace
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")


@router.post(
    "/switch-workspace/",
    response_model=SwitchWorkspaceResponse,
    status_code=status.HTTP_200_OK,
    summary="Switch to different workspace",
    description="""
    Switch authenticated user to a different workspace.

    User must be an active member of the target workspace.
    Returns new JWT token with updated workspace context.
    """
)
def switch_workspace(
    body: SwitchWorkspaceRequest,
    request: Request,
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Switch to a different workspace.

    Returns a NEW token pair (access + refresh) with the new workspace context.

    Raises:
        - 401 Unauthorized: User not authenticated
        - 403 Forbidden: User not member of target workspace
    """
    try:
        user_agent, ip_address = _client_context(request)
        workspace, token_pair, messages = auth_service.switch_workspace(
            db=db,
            user_id=current_user.id,
            workspace_id=body.workspace_id,
            user_agent=user_agent,
            ip_address=ip_address,
        )

        return SwitchWorkspaceResponse(
            access_token=token_pair.access_token,
            refresh_token=token_pair.refresh_token,
            token_type="bearer",
            expires_in=token_pair.expires_in,
            refresh_expires_in=token_pair.refresh_expires_in,
            workspace={
                "id": workspace.id,
                "name": workspace.name,
                "slug": workspace.slug
            },
            messages=[msg.model_dump() for msg in messages]
        )

    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Workspace switch failed: {str(e)}")


# ============================================================================
# PASSWORD RESET ENDPOINTS
# ============================================================================

@router.post(
    "/forgot-password/",
    response_model=ForgotPasswordResponse,
    status_code=status.HTTP_200_OK,
    summary="Request password reset",
    description="""
    Request password reset for user account.

    Sends password reset email with token (if user exists).
    Always returns success to prevent email enumeration attacks.

    **Note**: Reset token should be sent via email, not in API response.
    """
)
def forgot_password(
    request: ForgotPasswordRequest,
    db: Session = Depends(get_db)
):
    """
    Request password reset.

    Generates reset token and sends email (implementation pending).

    Note:
        Always returns success message, even if email doesn't exist
        (security best practice to prevent email enumeration).
    """
    try:
        reset_token, expires_at, messages = auth_service.request_password_reset(
            db=db,
            email=request.email
        )

        # TODO: Send email with reset token
        # email_service.send_password_reset_email(
        #     to=request.email,
        #     reset_token=reset_token,
        #     expires_at=expires_at
        # )

        return ForgotPasswordResponse(
            message="If an account with that email exists, a password reset link has been sent."
        )

    except Exception as e:
        # Don't reveal error details for security
        return ForgotPasswordResponse(
            message="If an account with that email exists, a password reset link has been sent."
        )


@router.post(
    "/reset-password/",
    response_model=ResetPasswordResponse,
    status_code=status.HTTP_200_OK,
    summary="Reset password with token",
    description="""
    Reset user password using reset token from email.

    Token must be:
    - Valid (not expired, not used)
    - From forgot-password endpoint

    **Note**: This endpoint requires password_reset_tokens table (TODO).
    """
)
def reset_password(
    request: ResetPasswordRequest,
    db: Session = Depends(get_db)
):
    """
    Reset password using reset token.

    Raises:
        - 400 Bad Request: Invalid or expired token
        - 501 Not Implemented: Password reset table not yet implemented
    """
    try:
        user, messages = auth_service.reset_password(
            db=db,
            reset_token=request.reset_token,
            new_password=request.new_password
        )

        return ResetPasswordResponse(
            message="Password reset successfully. You can now login with your new password.",
            messages=[msg.model_dump() for msg in messages]
        )

    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Password reset failed: {str(e)}")


@router.post(
    "/admin/reset-password/",
    response_model=AdminResetPasswordResponse,
    status_code=status.HTTP_200_OK,
    summary="Admin reset user password",
    description="""
    Workspace owner can reset another user's password.

    Business rules:
    - Only workspace owners can reset passwords
    - Target user must be in same workspace
    - Cannot reset owner's password unless you are owner
    """
)
def admin_reset_password(
    request: AdminResetPasswordRequest,
    current_user: Profile = Depends(get_current_active_user),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """
    Admin resets another user's password.

    Requires workspace owner permissions.

    Raises:
        - 403 Forbidden: Not workspace owner
        - 404 Not Found: Target user not found
    """
    try:
        target_user, messages = auth_service.reset_password_by_admin(
            db=db,
            admin_user_id=current_user.id,
            target_user_id=request.target_user_id,
            new_password=request.new_password,
            workspace_id=workspace.id
        )

        return AdminResetPasswordResponse(
            message=f"Password reset successfully for user: {target_user.email}",
            user_email=target_user.email,
            messages=[msg.model_dump() for msg in messages]
        )

    except ValueError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Admin password reset failed: {str(e)}")


# ============================================================================
# INVITATION VALIDATION ENDPOINTS
# ============================================================================

@router.post(
    "/validate-invitation/",
    response_model=ValidateInvitationResponse,
    status_code=status.HTTP_200_OK,
    summary="Validate invitation token",
    description="""
    Validate invitation token without accepting it.

    Returns invitation details:
    - Workspace name
    - Role
    - Inviter name
    - Expiration date

    Useful for showing invitation preview before user registers.
    """
)
def validate_invitation(
    request: ValidateInvitationRequest,
    db: Session = Depends(get_db)
):
    """
    Validate invitation token.

    Returns invitation details without accepting.

    Raises:
        - 400 Bad Request: Invalid, expired, or already used token
    """
    try:
        details, messages = auth_service.validate_invitation_token(
            db=db,
            invitation_token=request.invitation_token
        )

        return ValidateInvitationResponse(
            valid=True,
            invitation=details,
            messages=[msg.model_dump() for msg in messages]
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Invitation validation failed: {str(e)}")


# ============================================================================
# UTILITY ENDPOINTS
# ============================================================================

@router.get(
    "/me/",
    summary="Get current user",
    description="Get currently authenticated user's profile and workspace info"
)
def get_current_user_info(
    current_user: Profile = Depends(get_current_active_user),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """
    Get current authenticated user.

    Returns user profile and current workspace details.
    """
    return {
        "user": {
            "id": current_user.id,
            "name": current_user.name,
            "email": current_user.email,
            "permission": current_user.permission,
            "position": current_user.position
        },
        "workspace": {
            "id": workspace.id,
            "name": workspace.name,
            "slug": workspace.slug
        }
    }


@router.post(
    "/refresh/",
    response_model=TokenPairResponse,
    status_code=status.HTTP_200_OK,
    summary="Exchange refresh token for new access + refresh pair",
    description="""
    Exchange a refresh token for a brand-new access + refresh pair.

    **Rotation:** the presented refresh token is revoked on success; a new
    refresh token is returned and must replace the old one client-side.

    **Reuse detection:** if a refresh token that has already been rotated is
    presented again, the entire token family is revoked (likely theft) and
    the user is forced to log in again everywhere.

    Returns 401 on any failure (invalid, expired, revoked, or reuse detected).
    """
)
def refresh(
    body: RefreshTokenRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Refresh the access token using a long-lived refresh token."""
    try:
        user_agent, ip_address = _client_context(request)
        token_pair, _ = auth_service.refresh_access_token(
            db=db,
            raw_refresh_token=body.refresh_token,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        return TokenPairResponse(
            access_token=token_pair.access_token,
            refresh_token=token_pair.refresh_token,
            token_type="bearer",
            expires_in=token_pair.expires_in,
            refresh_expires_in=token_pair.refresh_expires_in,
        )
    except ValueError as e:
        # Don't leak which specific failure (invalid vs expired vs reused) to
        # the network. Server logs have the detail; client just gets 401.
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Token refresh failed: {str(e)}")


@router.post(
    "/logout/",
    status_code=status.HTTP_200_OK,
    summary="Revoke a refresh token (logout)",
    description="""
    Revoke the presented refresh token (default) or every active refresh
    token for the user (when `all_devices=true`).

    Best-effort: unknown or already-revoked tokens succeed silently. The
    client should always clear its in-memory + persisted tokens regardless
    of this endpoint's response.
    """,
)
def logout(
    body: LogoutRequest,
    db: Session = Depends(get_db),
):
    """Revoke the refresh token (this device, or all devices).

    Note: this endpoint does NOT require an access token. A stale/expired
    access token shouldn't block logout — the client just needs to drop the
    refresh token from the DB so it can't be used by anyone.
    """
    try:
        # For `all_devices=True` we need to know who the user is. We resolve
        # that by hashing the presented refresh token and looking it up — this
        # avoids requiring a valid (un-expired) access token to log out.
        user_id = None
        if body.all_devices:
            if not body.refresh_token:
                raise HTTPException(
                    status_code=400,
                    detail="refresh_token is required for all_devices logout",
                )
            from app.core.security import hash_refresh_token
            from app.dao.refresh_token import refresh_token_dao
            row = refresh_token_dao.get_by_hash(
                db, token_hash=hash_refresh_token(body.refresh_token)
            )
            if row:
                user_id = row.user_id
            # If the row is unknown we still 200 — treat as already logged out.

        messages = auth_service.logout_session(
            db=db,
            raw_refresh_token=body.refresh_token,
            user_id=user_id,
            all_devices=body.all_devices,
        )

        return {
            "message": "Logged out.",
            "messages": [msg.model_dump() for msg in messages],
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Logout failed: {str(e)}")
