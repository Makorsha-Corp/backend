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
from fastapi import APIRouter, Depends, status, HTTPException
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
)
from app.services.auth_service import auth_service
from app.models.profile import Profile
from app.models.workspace import Workspace


router = APIRouter()


# ============================================================================
# REGISTRATION ENDPOINTS
# ============================================================================

@router.post(
    "/register",
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
    request: RegisterRequest,
    db: Session = Depends(get_db)
):
    """
    Register a new user.

    Either workspace_name OR invitation_token must be provided.
    Returns access token, user, workspace, and messages.

    Raises:
        - 409 Conflict: Email already registered
        - 400 Bad Request: Validation errors
    """
    try:
        user, workspace, jwt_token, messages = auth_service.register_user(
            db=db,
            name=request.name,
            email=request.email,
            password=request.password,
            position=request.position,
            workspace_name=request.workspace_name,
            invitation_token=request.invitation_token
        )

        return RegisterResponse(
            access_token=jwt_token,
            token_type="bearer",
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
    "/login",
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
    db: Session = Depends(get_db)
):
    """
    Login with email and password (workspace selection happens after).

    Returns:
        - access_token: JWT token for authentication
        - token_type: Always "bearer"
        - user: User profile data
        - messages: Informational messages

    Raises:
        - 401 Unauthorized: Invalid credentials
    """
    try:
        user, jwt_token, messages = auth_service.login_user(
            db=db,
            email=credentials.email,
            password=credentials.password
        )

        return LoginResponse(
            access_token=jwt_token,
            token_type="bearer",
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
    "/switch-workspace",
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
    request: SwitchWorkspaceRequest,
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Switch to a different workspace.

    Returns new JWT token with new workspace context.

    Raises:
        - 401 Unauthorized: User not authenticated
        - 403 Forbidden: User not member of target workspace
    """
    try:
        workspace, jwt_token, messages = auth_service.switch_workspace(
            db=db,
            user_id=current_user.id,
            workspace_id=request.workspace_id
        )

        return SwitchWorkspaceResponse(
            access_token=jwt_token,
            token_type="bearer",
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
    "/forgot-password",
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
    "/reset-password",
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
    "/admin/reset-password",
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
    "/validate-invitation",
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
    "/me",
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
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="User logout",
    description="""
    Logout current user.

    **Note**: Since we're using stateless JWT, logout is handled client-side
    by deleting the token. This endpoint is a placeholder for potential
    future token blacklisting or session management.
    """
)
def logout():
    """
    Logout user (client-side operation).

    Frontend should delete the JWT token from storage.

    Future: Could implement token blacklist here.
    """
    return {
        "message": "Logged out successfully. Please delete your token on the client side."
    }
