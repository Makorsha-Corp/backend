"""Authentication schemas"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime


class Token(BaseModel):
    """Token response schema"""
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Token payload schema"""
    sub: int | None = None
    email: str | None = None
    workspace_id: int | None = None


# ============================================================================
# REGISTRATION SCHEMAS
# ============================================================================

class RegisterRequest(BaseModel):
    """Registration request schema"""
    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=72)
    position: str = Field(default="User", max_length=100)
    workspace_name: Optional[str] = Field(None, min_length=1, max_length=255)
    invitation_token: Optional[str] = None


class RegisterResponse(BaseModel):
    """Registration response schema"""
    access_token: str
    token_type: str = "bearer"
    user: dict
    workspace: dict
    messages: list[dict] = []


# ============================================================================
# LOGIN SCHEMAS
# ============================================================================

class LoginRequest(BaseModel):
    """Login request schema (workspace selection happens after login)"""
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    """Login response schema (workspace NOT included - user selects after login)"""
    access_token: str
    token_type: str = "bearer"
    user: dict
    messages: list[dict] = []


class SwitchWorkspaceRequest(BaseModel):
    """Switch workspace request schema"""
    workspace_id: int


class SwitchWorkspaceResponse(BaseModel):
    """Switch workspace response schema"""
    access_token: str
    token_type: str = "bearer"
    workspace: dict
    messages: list[dict] = []


# ============================================================================
# PASSWORD RESET SCHEMAS
# ============================================================================

class ForgotPasswordRequest(BaseModel):
    """Forgot password request schema"""
    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    """Forgot password response schema"""
    message: str
    # Note: reset_token should be sent via email, not in response


class ResetPasswordRequest(BaseModel):
    """Reset password request schema"""
    reset_token: str
    new_password: str = Field(..., min_length=8, max_length=72)


class ResetPasswordResponse(BaseModel):
    """Reset password response schema"""
    message: str
    messages: list[dict] = []


class AdminResetPasswordRequest(BaseModel):
    """Admin reset password request schema"""
    target_user_id: int
    new_password: str = Field(..., min_length=8, max_length=72)


class AdminResetPasswordResponse(BaseModel):
    """Admin reset password response schema"""
    message: str
    user_email: str
    messages: list[dict] = []


# ============================================================================
# INVITATION VALIDATION SCHEMAS
# ============================================================================

class ValidateInvitationRequest(BaseModel):
    """Validate invitation request schema"""
    invitation_token: str


class ValidateInvitationResponse(BaseModel):
    """Validate invitation response schema"""
    valid: bool = True
    invitation: dict
    messages: list[dict] = []
