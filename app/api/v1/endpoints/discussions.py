"""Universal discussion endpoints."""
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_active_user, get_current_workspace, get_db
from app.models.enums import DiscussionEntityType
from app.models.profile import Profile
from app.models.workspace import Workspace
from app.schemas.discussion import (
    DiscussionCreate,
    DiscussionListResponse,
    DiscussionResponse,
)
from app.services.discussion_service import discussion_service

router = APIRouter()


@router.get("/", response_model=DiscussionListResponse, status_code=status.HTTP_200_OK)
def list_discussions(
    entity_type: DiscussionEntityType = Query(...),
    entity_id:   int                  = Query(...),
    skip:        int                  = Query(0, ge=0),
    limit:       int                  = Query(50, ge=1, le=200),
    db:          Session              = Depends(get_db),
    workspace:   Workspace            = Depends(get_current_workspace),
    current_user: Profile             = Depends(get_current_active_user),
):
    items, total = discussion_service.list(
        db, workspace.id, entity_type, entity_id, skip, limit
    )
    return DiscussionListResponse(items=items, total=total)


@router.post("/", response_model=DiscussionResponse, status_code=status.HTTP_201_CREATED)
def create_discussion(
    data:         DiscussionCreate = ...,
    db:           Session          = Depends(get_db),
    workspace:    Workspace        = Depends(get_current_workspace),
    current_user: Profile          = Depends(get_current_active_user),
):
    return discussion_service.create(
        db=db,
        workspace_id=workspace.id,
        user_id=current_user.id,
        data=data,
    )
