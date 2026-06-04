"""
FastAPI dependencies for dependency injection
"""
from typing import Generator, Optional
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.core.security import decode_token
from app.models.profile import Profile
from app.models.workspace import Workspace
from app.dao.workspace import workspace_dao
from app.dao.workspace_member import workspace_member_dao


security = HTTPBearer()


def get_db() -> Generator:
    """
    Database session dependency

    Yields:
        Database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> Profile:
    """
    Get current authenticated user from JWT token

    Args:
        credentials: HTTP authorization credentials
        db: Database session

    Returns:
        Current user profile

    Raises:
        HTTPException: If authentication fails
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = credentials.credentials
    payload = decode_token(token)

    if payload is None:
        raise credentials_exception

    user_id_str: Optional[str] = payload.get("sub")

    if user_id_str is None:
        raise credentials_exception

    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        raise credentials_exception

    user = db.query(Profile).filter(Profile.id == user_id).first()

    if user is None:
        raise credentials_exception

    return user


def get_current_active_user(
    current_user: Profile = Depends(get_current_user)
) -> Profile:
    """
    Get current active user

    Args:
        current_user: Current user from token

    Returns:
        Current active user

    Raises:
        HTTPException: If user is inactive
    """
    # Add any additional checks here (e.g., user.is_active)
    return current_user


def get_current_workspace(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Profile = Depends(get_current_user)
) -> Workspace:
    """
    Get current workspace from X-Workspace-ID header and validate user access

    Args:
        request: FastAPI request object
        db: Database session
        current_user: Current authenticated user

    Returns:
        Current workspace

    Raises:
        HTTPException: If workspace ID is missing, invalid, not found, or user lacks access
    """
    # Get workspace ID from header
    workspace_id_header = request.headers.get("x-workspace-id")
    
    if not workspace_id_header:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Workspace-ID header is required"
        )
    
    # Validate workspace ID is a valid integer
    try:
        workspace_id = int(workspace_id_header)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Workspace-ID must be a valid integer"
        )
    
    # Get workspace from database
    workspace = workspace_dao.get(db, id=workspace_id)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workspace with ID {workspace_id} not found"
        )
    
    # Validate user has access to workspace
    if not workspace_member_dao.has_access(
        db, user_id=current_user.id, workspace_id=workspace_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this workspace"
        )
    
    return workspace
