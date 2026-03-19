"""Project endpoints"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.deps import get_db, get_current_active_user, get_current_workspace
from app.models.profile import Profile
from app.models.workspace import Workspace
from app.schemas.project import ProjectCreate, ProjectUpdate, ProjectResponse
from app.services.project_service import project_service


router = APIRouter()


@router.get(
    "",
    response_model=List[ProjectResponse],
    status_code=status.HTTP_200_OK,
    summary="List all projects",
    description="Get all projects in the workspace with optional filters"
)
def get_projects(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    factory_id: Optional[int] = Query(None, description="Filter by factory ID"),
    project_status: Optional[str] = Query(None, description="Filter by project status"),
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Get all projects in workspace with optional filters"""
    projects = project_service.list_projects(
        db,
        workspace_id=workspace.id,
        factory_id=factory_id,
        status=project_status,
        skip=skip,
        limit=limit
    )
    return projects


@router.get(
    "/{project_id}",
    response_model=ProjectResponse,
    status_code=status.HTTP_200_OK,
    summary="Get project by ID",
    description="Get a specific project by ID"
)
def get_project(
    project_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    db: Session = Depends(get_db)
):
    """Get a specific project"""
    project = project_service.get_project(
        db,
        project_id=project_id,
        workspace_id=workspace.id
    )
    return project


@router.post(
    "",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new project",
    description="Create a new project"
)
def create_project(
    project_in: ProjectCreate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Create a new project"""
    try:
        project = project_service.create_project(
            db,
            project_in=project_in,
            workspace_id=workspace.id,
            user_id=current_user.id
        )
        return project
    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR creating project: {str(e)}")
        print(f"Project data: {project_in}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.put(
    "/{project_id}",
    response_model=ProjectResponse,
    status_code=status.HTTP_200_OK,
    summary="Update project",
    description="Update an existing project"
)
def update_project(
    project_id: int,
    project_in: ProjectUpdate,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Update a project"""
    project = project_service.update_project(
        db,
        project_id=project_id,
        project_in=project_in,
        workspace_id=workspace.id,
        user_id=current_user.id
    )
    return project


@router.delete(
    "/{project_id}",
    response_model=ProjectResponse,
    status_code=status.HTTP_200_OK,
    summary="Soft delete project",
    description="Soft delete a project (sets is_deleted flag)"
)
def delete_project(
    project_id: int,
    workspace: Workspace = Depends(get_current_workspace),
    current_user: Profile = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """Soft delete a project"""
    project = project_service.delete_project(
        db,
        project_id=project_id,
        workspace_id=workspace.id,
        user_id=current_user.id
    )
    return project
