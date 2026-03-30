"""
Account Tag endpoints

Provides operations for managing account tags (categories for accounts).
"""
from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_workspace, get_current_active_user
from app.models.workspace import Workspace
from app.models.profile import Profile
from app.schemas.account_tag import AccountTagCreate, AccountTagUpdate, AccountTagResponse
from app.services.account_tag_service import account_tag_service


router = APIRouter()


@router.get(
    "/",
    response_model=List[AccountTagResponse],
    status_code=status.HTTP_200_OK,
    summary="List all tags",
    description="""
    Get all active account tags in the workspace.

    Returns both system tags and user-created tags, sorted with system tags first.
    """
)
def get_tags(
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Get all active tags in the workspace"""
    return account_tag_service.get_tags(db, workspace_id=workspace.id)


@router.get(
    "/system/",
    response_model=List[AccountTagResponse],
    status_code=status.HTTP_200_OK,
    summary="List system tags",
    description="Get all system tags (default tags that cannot be deleted)"
)
def get_system_tags(
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Get all system tags in the workspace"""
    return account_tag_service.get_system_tags(db, workspace_id=workspace.id)


@router.post(
    "/",
    response_model=AccountTagResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new tag",
    description="Create a new custom tag for categorizing accounts"
)
def create_tag(
    tag_in: AccountTagCreate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create new custom tag"""
    return account_tag_service.create_tag(db, tag_in=tag_in, workspace_id=workspace.id, user_id=current_user.id)


@router.put(
    "/{tag_id}/",
    response_model=AccountTagResponse,
    status_code=status.HTTP_200_OK,
    summary="Update tag",
    description="Update a tag (only user-created tags can be updated, not system tags)"
)
def update_tag(
    tag_id: int,
    tag_in: AccountTagUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Update tag"""
    return account_tag_service.update_tag(db, tag_id=tag_id, tag_in=tag_in, workspace_id=workspace.id)


@router.delete(
    "/{tag_id}/",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete tag",
    description="Delete a tag (only user-created tags can be deleted, not system tags)"
)
def delete_tag(
    tag_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Delete tag (soft delete)"""
    account_tag_service.delete_tag(db, tag_id=tag_id, workspace_id=workspace.id)
