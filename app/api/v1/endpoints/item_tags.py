"""
Item Tag endpoints

Provides operations for managing item tags (categories for items).
"""
from typing import List
from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_workspace, get_current_active_user
from app.models.workspace import Workspace
from app.models.profile import Profile
from app.schemas.item_tag import ItemTagCreate, ItemTagUpdate, ItemTagResponse
from app.dao.item_tag import item_tag_dao


router = APIRouter()


@router.get(
    "/",
    response_model=List[ItemTagResponse],
    status_code=status.HTTP_200_OK,
    summary="List all tags",
    description="""
    Get all active item tags in the workspace.

    Returns both system tags and user-created tags, sorted with system tags first.
    """
)
def get_tags(
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Get all active tags in the workspace"""
    tags = item_tag_dao.get_active_tags_in_workspace(db, workspace_id=workspace.id)
    return tags


@router.get(
    "/system",
    response_model=List[ItemTagResponse],
    status_code=status.HTTP_200_OK,
    summary="List system tags",
    description="Get all system tags (default tags that cannot be deleted)"
)
def get_system_tags(
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Get all system tags in the workspace"""
    tags = item_tag_dao.get_system_tags_in_workspace(db, workspace_id=workspace.id)
    return tags


@router.post(
    "/",
    response_model=ItemTagResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new tag",
    description="Create a new custom tag for categorizing items"
)
def create_tag(
    tag_in: ItemTagCreate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create new custom tag"""
    # Auto-generate tag_code from name if not provided
    tag_code = tag_in.tag_code
    if not tag_code:
        # Generate tag_code: lowercase, replace spaces with underscores, remove special chars
        tag_code = tag_in.name.lower().replace(' ', '_')
        tag_code = ''.join(c for c in tag_code if c.isalnum() or c == '_')

    # Check if tag with same code already exists
    existing = item_tag_dao.get_by_code_in_workspace(db, workspace_id=workspace.id, tag_code=tag_code)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Tag with code '{tag_code}' already exists"
        )

    # Create tag
    tag_data = tag_in.model_dump()
    tag_data['tag_code'] = tag_code  # Use generated or provided code
    tag_data['workspace_id'] = workspace.id
    tag_data['created_by'] = current_user.id
    tag_data['is_system_tag'] = False  # User-created tags are never system tags
    tag_data['usage_count'] = 0

    tag = item_tag_dao.create(db, obj_in=tag_data)
    db.commit()
    db.refresh(tag)

    return tag


@router.put(
    "/{tag_id}",
    response_model=ItemTagResponse,
    status_code=status.HTTP_200_OK,
    summary="Update tag",
    description="Update a tag (only user-created tags can be updated, not system tags)"
)
def update_tag(
    tag_id: int,
    tag_in: ItemTagUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Update tag"""
    tag = item_tag_dao.get_by_id_and_workspace(db, id=tag_id, workspace_id=workspace.id)
    if not tag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")

    if tag.is_system_tag:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System tags cannot be modified"
        )

    updated_tag = item_tag_dao.update(db, db_obj=tag, obj_in=tag_in)
    db.commit()
    db.refresh(updated_tag)

    return updated_tag


@router.delete(
    "/{tag_id}",
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
    tag = item_tag_dao.get_by_id_and_workspace(db, id=tag_id, workspace_id=workspace.id)
    if not tag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")

    if tag.is_system_tag:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System tags cannot be deleted"
        )

    # Soft delete
    item_tag_dao.update(db, db_obj=tag, obj_in={"is_active": False})
    db.commit()
