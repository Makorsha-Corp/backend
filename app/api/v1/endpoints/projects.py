"""Project endpoints"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_active_user, get_current_workspace
from app.models.profile import Profile
from app.models.workspace import Workspace
from app.dao.profile import profile_dao
from app.dao.workspace_member import workspace_member_dao
from app.schemas.project import (
    ProjectCreate,
    ProjectUpdate,
    ProjectResponse,
    ProjectMemberCreate,
    ProjectMemberResponse,
    ProjectMembersListResponse,
    ProjectVisibilityUpdate,
    ProjectEventMetadata,
    ProjectEventResponse,
)
from app.services.project_service import project_service


def _member_response(record, profile=None, position=None) -> ProjectMemberResponse:
    return ProjectMemberResponse(
        id=record.id,
        workspace_id=record.workspace_id,
        project_id=record.project_id,
        user_id=record.user_id,
        user_name=profile.name if profile else None,
        user_email=profile.email if profile else None,
        user_position=position,
        assigned_by=record.assigned_by,
        assigned_at=record.assigned_at,
    )


router = APIRouter()


@router.get(
    "/",
    response_model=List[ProjectResponse],
    status_code=status.HTTP_200_OK,
    summary="List all projects",
    description="Get all projects in the workspace with optional filters",
)
def get_projects(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    factory_id: Optional[int] = Query(None, description="Filter by factory ID"),
    project_status: Optional[str] = Query(None, description="Filter by project status"),
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return project_service.list_projects(
        db,
        workspace_id=workspace.id,
        user_id=current_user.id,
        factory_id=factory_id,
        status=project_status,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{project_id}/",
    response_model=ProjectResponse,
    status_code=status.HTTP_200_OK,
    summary="Get project by ID",
)
def get_project(
    project_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return project_service.get_project(
        db,
        project_id=project_id,
        workspace_id=workspace.id,
        user_id=current_user.id,
    )


@router.post(
    "/",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new project",
)
def create_project(
    project_in: ProjectCreate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    try:
        return project_service.create_project(
            db,
            project_in=project_in,
            workspace_id=workspace.id,
            user_id=current_user.id,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.put(
    "/{project_id}/",
    response_model=ProjectResponse,
    status_code=status.HTTP_200_OK,
    summary="Update project",
)
def update_project(
    project_id: int,
    project_in: ProjectUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return project_service.update_project(
        db,
        project_id=project_id,
        project_in=project_in,
        workspace_id=workspace.id,
        user_id=current_user.id,
    )


@router.delete(
    "/{project_id}/",
    response_model=ProjectResponse,
    status_code=status.HTTP_200_OK,
    summary="Soft delete project",
)
def delete_project(
    project_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return project_service.delete_project(
        db,
        project_id=project_id,
        workspace_id=workspace.id,
        user_id=current_user.id,
    )


# ─── Project Members ───────────────────────────────────────────

@router.get(
    "/{project_id}/members/",
    response_model=ProjectMembersListResponse,
    status_code=status.HTTP_200_OK,
    summary="List project members",
)
def list_project_members(
    project_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    records = project_service.list_members(
        db,
        project_id=project_id,
        workspace_id=workspace.id,
        user_id=current_user.id,
    )
    members = []
    for record in records:
        profile = profile_dao.get(db, id=record.user_id)
        member = workspace_member_dao.get_by_workspace_and_user(
            db, workspace_id=workspace.id, user_id=record.user_id
        )
        members.append(
            _member_response(record, profile, member.position if member else None)
        )
    return ProjectMembersListResponse(members=members)


@router.post(
    "/{project_id}/members/",
    response_model=ProjectMemberResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a member to a project",
)
def add_project_member(
    project_id: int,
    body: ProjectMemberCreate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    record = project_service.add_member(
        db,
        project_id=project_id,
        member_user_id=body.user_id,
        workspace_id=workspace.id,
        assigned_by=current_user.id,
    )
    profile = profile_dao.get(db, id=record.user_id)
    member = workspace_member_dao.get_by_workspace_and_user(
        db, workspace_id=workspace.id, user_id=record.user_id
    )
    return _member_response(record, profile, member.position if member else None)


@router.delete(
    "/{project_id}/members/{user_id}/",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a member from a project",
)
def remove_project_member(
    project_id: int,
    user_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    project_service.remove_member(
        db,
        project_id=project_id,
        member_user_id=user_id,
        workspace_id=workspace.id,
        performed_by=current_user.id,
    )


@router.patch(
    "/{project_id}/visibility/",
    response_model=ProjectResponse,
    status_code=status.HTTP_200_OK,
    summary="Update project visibility",
)
def update_project_visibility(
    project_id: int,
    body: ProjectVisibilityUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return project_service.set_visibility(
        db,
        project_id=project_id,
        visibility=body.visibility,
        workspace_id=workspace.id,
        user_id=current_user.id,
    )


# ─── Project Events ────────────────────────────────────────────

@router.get(
    "/{project_id}/events/",
    response_model=List[ProjectEventResponse],
    status_code=status.HTTP_200_OK,
    summary="List project activity events",
)
def list_project_events(
    project_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    rows = project_service.list_events(
        db,
        project_id=project_id,
        workspace_id=workspace.id,
        user_id=current_user.id,
    )
    return [
        ProjectEventResponse(
            id=e.id,
            workspace_id=e.workspace_id,
            project_id=e.project_id,
            event_type=e.event_type,
            description=e.description,
            metadata=(
                ProjectEventMetadata.model_validate(e.metadata_json)
                if e.metadata_json
                else None
            ),
            performed_by=e.performed_by,
            user_name=profile.name if profile else None,
            created_at=e.created_at,
        )
        for e, profile in rows
    ]
